#!/usr/bin/python3

import enum
import logging
import os
import pickle
import select
import signal
import sys
import time
import traceback
import threading

from . import ipc

logger = logging.getLogger(__name__)


# TODO
# - message passing


class ProcessState(enum.Enum):
    NOT_STARTED = 'not_started'
    RUNNING = 'running'
    FINISHED = 'finished'


class OutputBuffer(object):
    def __init__(self, handler):
        self._buf = bytearray()
        self._handler = handler

    def append(self, data):
        self._buf.extend(data)
        self.emit()

    def emit(self):
        while True:
            try:
                eol = self._buf.index(b'\n')
            except ValueError:
                return

            line = self._buf[:eol+1]
            self._buf = self._buf[eol+1:]
            self._handler(bytes(line))

    def flush(self):
        self.emit()
        if self._buf:
            self._handler(bytes(self._buf))
            self._buf.clear()


class ProcessManager(object):
    def __init__(self):
        self._processes = {}
        self._fd_map = {}
        self._shutting_down = threading.Event()
        self._old_sigchld_handler = None
        self._output_poller = None
        self._output_poll_thread = None

        self._server = ipc.Server('manager')

    def setup(self):
        self._old_sigchld_handler = signal.signal(
            signal.SIGCHLD, self.sigchld_handler)

        self._output_poller = select.epoll()
        self._output_poll_thread = threading.Thread(
            target=self._collect_output)
        self._output_poll_thread.start()

        self._server.setup()
        self._server.start()

    def cleanup(self):
        self._shutting_down.set()

        self.terminate_all_children()

        self._server.cleanup()

        if self._old_sigchld_handler is not None:
            signal.signal(signal.SIGCHLD, self._old_sigchld_handler)
            self._old_sigchld_handler = None

        if self._output_poll_thread is not None:
            self._output_poll_thread.join()
            self._output_poll_thread = None

        if self._output_poller is not None:
            self._output_poller = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False

    def terminate_all_children(self, timeout=10):
        sigchld_event = threading.Event()
        old_sigchld_handler = signal.signal(
            signal.SIGCHLD, lambda sig, frame: sigchld_event.set())
        try:
            for sig in [signal.SIGTERM, signal.SIGKILL]:
                for pid in list(self._processes.keys()):
                    logger.warning(
                        "Sending %s to left over child pid=%d",
                        sig.name, pid)
                    os.kill(pid, sig)

                deadline = time.time() + timeout
                while time.time() < deadline:
                    self.collect_dead_children()
                    if not self._processes:
                        break
                    logger.info(
                        ("%d children still running, waiting for SIGCHLD"
                         " signal..."), len(self._processes))
                    sigchld_event.wait(min(0.05, timeout))

            for pid in self._processes.keys():
                logger.error("Failed to kill child pid=%d", pid)
        finally:
            signal.signal(signal.SIGCHLD, old_sigchld_handler)

    def start_process(self, name, cls, *args, **kwargs):
        assert issubclass(cls, ProcessImpl)

        barrier_in, barrier_out = os.pipe()
        announce_in, announce_out = os.pipe()
        stdout_in, stdout_out = os.pipe2(os.O_NONBLOCK)
        stderr_in, stderr_out = os.pipe2(os.O_NONBLOCK)

        manager_address = self._server.address

        pid = os.fork()
        if pid == 0:
            # In child process.
            os.close(barrier_out)
            os.close(announce_in)

            os.dup2(stdout_out, 1)
            os.dup2(stderr_out, 2)

            # Wait until manager told us it's ok to start. Avoid race
            # condition where child terminates and generates SIGCHLD
            # before manager has added it to its process map.
            os.read(barrier_in, 1)
            os.close(barrier_in)

            impl = cls(name, manager_address)

            # TODO: if crashes before ready_callback was sent, write
            # back failure message to pipe.
            def ready_callback():
                stub_address = impl.server.address.encode('utf-8')
                while stub_address:
                    written = os.write(announce_out, stub_address)
                    stub_address = stub_address[written:]
                os.close(announce_out)

            try:
                try:
                    rc = impl.main(ready_callback, *args, **kwargs)
                except:
                    traceback.print_exc()
                    rc = 1
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(rc or 0)

        else:
            # In manager process.
            os.close(barrier_in)
            os.close(announce_out)

            logger.info("Created new subprocess pid=%d.", pid)
            stub = ProcessStub(pid, stdout_in, stderr_in)
            self._processes[pid] = stub

            self._fd_map[stdout_in] = OutputBuffer(stub.handle_stdout)
            self._output_poller.register(
                stdout_in, select.POLLIN | select.POLLERR | select.POLLHUP)
            self._fd_map[stderr_in] = OutputBuffer(stub.handle_stderr)
            self._output_poller.register(
                stderr_in, select.POLLIN | select.POLLERR | select.POLLHUP)

            # Unleash the child.
            stub.state = ProcessState.RUNNING
            os.write(barrier_out, b'1')
            os.close(barrier_out)

            # Wait for it to write back its server address.
            # TODO: need to timeout? what happens when child terminates
            # before full address is written?
            stub_address = b''
            while True:
                read = os.read(announce_in, 1024)
                if not read:
                    break
                stub_address += read
            os.close(announce_in)
            stub.address = stub_address.decode('utf-8')
            logger.info(
                "Child pid=%d has IPC address %s", pid, stub.address)

            return stub

    def sigchld_handler(self, num, frame):
        assert num == signal.SIGCHLD
        self.collect_dead_children()

    def collect_dead_children(self):
        dead_children = set()
        for pid, stub in self._processes.items():
            pid, rc, resinfo = os.wait4(pid, os.WNOHANG)
            if pid == 0:
                continue

            logger.info("Child pid=%d terminated with rc=%d", pid, rc)

            try:
                stub = self._processes[pid]
            except KeyError:
                logger.warning("Unknown child pid=%d", pid)
                continue

            if stub.state != ProcessState.RUNNING:
                logger.error(
                    "Child pid=%d: Unexpected state %s",
                    pid, stub.state)
                continue

            logger.info("Child pid=%d resource usage:", pid)
            logger.info("  utime=%f", resinfo.ru_utime)
            logger.info("  stime=%f", resinfo.ru_stime)
            logger.info("  maxrss=%d", resinfo.ru_maxrss)
            logger.info("  ixrss=%d", resinfo.ru_ixrss)
            logger.info("  idrss=%d", resinfo.ru_idrss)
            logger.info("  isrss=%d", resinfo.ru_isrss)
            logger.info("  minflt=%d", resinfo.ru_minflt)
            logger.info("  majflt=%d", resinfo.ru_majflt)
            logger.info("  nswap=%d", resinfo.ru_nswap)
            logger.info("  inblock=%d", resinfo.ru_inblock)
            logger.info("  oublock=%d", resinfo.ru_oublock)
            logger.info("  msgsnd=%d", resinfo.ru_msgsnd)
            logger.info("  msgrcv=%d", resinfo.ru_msgrcv)
            logger.info("  nsignals=%d", resinfo.ru_nsignals)
            logger.info("  nvcsw=%d", resinfo.ru_nvcsw)
            logger.info("  nivcsw=%d", resinfo.ru_nivcsw)

            stub.state = ProcessState.FINISHED
            stub.returncode = rc

            for fd in [stub.stdout, stub.stderr]:
                self._output_poller.unregister(fd)
                self._fd_map[fd].flush()
                del self._fd_map[fd]
                os.close(fd)
            stub.stdout = None
            stub.stderr = None

            dead_children.add(pid)

        for pid in dead_children:
            del self._processes[pid]

    def _collect_output(self):
        while not self._shutting_down.is_set():
            for fd, event in self._output_poller.poll(0.1):
                if event & select.POLLIN:
                    try:
                        buf = self._fd_map[fd]
                    except KeyError:
                        logger.error("poll() returned unknown FD %d", fd)
                        continue

                    while True:
                        try:
                            data = os.read(fd, 1024)
                        except BlockingIOError:
                            break
                        buf.append(data)


class ProcessImpl(object):
    def __init__(self, name, manager_address):
        self.name = name
        self.pid = os.getpid()

        self.manager = ManagerStub(manager_address)
        self.server = ipc.Server(name)

    def main(self, ready_callback, *args, **kwargs):
        with self.manager:
            with self.server:
                self.server.start()
                try:
                    self.setup()
                    ready_callback()

                    self.run(*args, **kwargs)
                finally:
                    self.cleanup()

    def setup(self):
        pass

    def cleanup(self):
        pass

    def run(self):
        raise NotImplementedError("Subclass must override run")


class ProcessStub(object):
    def __init__(self, pid, stdout, stderr):
        self.state = ProcessState.NOT_STARTED
        self.pid = pid
        self.address = None
        self.returncode = None
        self.stdout = stdout
        self.stderr = stderr

    def handle_stdout(self, data):
        logger = logging.getLogger('childproc[%d].stdout' % self.pid)
        logger.info(
            data.rstrip(b'\n').decode(
                sys.stdout.encoding, 'backslashreplace'))

    def handle_stderr(self, data):
        logger = logging.getLogger('childproc[%d].stderr' % self.pid)
        logger.info(
            data.rstrip(b'\n').decode(
                sys.stdout.encoding, 'backslashreplace'))

    def wait(self):
        while True:
            if self.state == ProcessState.FINISHED:
                return
            time.sleep(0.1)


class ManagerStub(ipc.Stub):
    pass
