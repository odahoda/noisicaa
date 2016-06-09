#!/usr/bin/python3

import asyncio
import enum
import functools
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


class ProcessState(enum.Enum):
    NOT_STARTED = 'not_started'
    RUNNING = 'running'
    FINISHED = 'finished'


class PipeAdapter(asyncio.Protocol):
    def __init__(self, handler):
        super().__init__()
        self._handler = handler
        self._buf = bytearray()

    def data_received(self, data):
        self._buf.extend(data)
        while True:
            eol = self._buf.find(b'\n')
            if eol < 0:
                break
            line = self._buf[:eol].decode('utf-8')
            del self._buf[:eol+1]
            self._handler(line)

    def eof_received(self):
        if self._buf:
            line = self._buf.decode('utf-8')
            del self._buf[:]
            self._handler(line)


class ProcessManager(object):
    def __init__(self, event_loop):
        self._event_loop = event_loop
        self._processes = {}
        # self._shutting_down = threading.Event()

        # self._server = ipc.Server('manager')
        pass
        
    def start(self):
        logger.info("Starting ProcessManager...")
        self._event_loop.add_signal_handler(
            signal.SIGCHLD, self.sigchld_handler)

    # def setup(self):
    #     self._old_sigchld_handler = signal.signal(
    #         signal.SIGCHLD, self.sigchld_handler)

    #     self._output_poller = select.epoll()
    #     self._output_poll_thread = threading.Thread(
    #         target=self._collect_output)
    #     self._output_poll_thread.start()

    #     self._server.setup()
    #     self._server.start()

    # def cleanup(self):
    #     self._shutting_down.set()

    #     self.terminate_all_children()

    #     self._server.cleanup()

    #     if self._old_sigchld_handler is not None:
    #         signal.signal(signal.SIGCHLD, self._old_sigchld_handler)
    #         self._old_sigchld_handler = None

    #     if self._output_poll_thread is not None:
    #         self._output_poll_thread.join()
    #         self._output_poll_thread = None

    #     if self._output_poller is not None:
    #         self._output_poller = None

    # def __enter__(self):
    #     self.setup()
    #     return self

    # def __exit__(self, exc_type, exc_val, exc_tb):
    #     self.cleanup()
    #     return False

    # def terminate_all_children(self, timeout=10):
    #     sigchld_event = threading.Event()
    #     old_sigchld_handler = signal.signal(
    #         signal.SIGCHLD, lambda sig, frame: sigchld_event.set())
    #     try:
    #         for sig in [signal.SIGTERM, signal.SIGKILL]:
    #             for pid in list(self._processes.keys()):
    #                 logger.warning(
    #                     "Sending %s to left over child pid=%d",
    #                     sig.name, pid)
    #                 os.kill(pid, sig)

    #             deadline = time.time() + timeout
    #             while time.time() < deadline:
    #                 self.collect_dead_children()
    #                 if not self._processes:
    #                     break
    #                 logger.info(
    #                     ("%d children still running, waiting for SIGCHLD"
    #                      " signal..."), len(self._processes))
    #                 sigchld_event.wait(min(0.05, timeout))

    #         for pid in self._processes.keys():
    #             logger.error("Failed to kill child pid=%d", pid)
    #     finally:
    #         signal.signal(signal.SIGCHLD, old_sigchld_handler)

    async def start_process(self, name, cls, *args, **kwargs):
        assert issubclass(cls, ProcessImpl)

        proc = ProcessHandle()

        barrier_in, barrier_out = os.pipe()
    #     announce_in, announce_out = os.pipe()
        stdout_in, stdout_out = os.pipe2(os.O_NONBLOCK)
        stderr_in, stderr_out = os.pipe2(os.O_NONBLOCK)

    #     manager_address = self._server.address

        pid = os.fork()
        if pid == 0:
            # In child process.

            # Close the "other ends" of the pipes.
            os.close(barrier_out)
    #         os.close(announce_in)
            os.close(stdout_in)
            os.close(stderr_in)

            # Use the pipes as out STDIN/-ERR.
            os.dup2(stdout_out, 1)
            os.dup2(stderr_out, 2)
            os.close(stdout_out)
            os.close(stderr_out)

            # TODO: ensure that sys.stdout/err use utf-8

            # Wait until manager told us it's ok to start. Avoid race
            # condition where child terminates and generates SIGCHLD
            # before manager has added it to its process map.
            os.read(barrier_in, 1)
            os.close(barrier_in)

            impl = cls(name)

    #         # TODO: if crashes before ready_callback was sent, write
    #         # back failure message to pipe.
    #         def ready_callback():
    #             stub_address = impl.server.address.encode('utf-8')
    #             while stub_address:
    #                 written = os.write(announce_out, stub_address)
    #                 stub_address = stub_address[written:]
    #             os.close(announce_out)

            try:
                try:
    #                 rc = impl.main(ready_callback, *args, **kwargs)
                    rc = impl.run(*args, **kwargs)
                except SystemExit as exc:
                    rc = exc.code
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
    #         os.close(announce_out)
            
            self._processes[pid] = proc

            proc.pid = pid
            proc.create_loggers()

            proc.logger.info("Created new subprocess.")

            await proc.setup_std_handlers(
                self._event_loop, stdout_in, stderr_in)

            # Unleash the child.
            proc.state = ProcessState.RUNNING

            # TODO: There's no simpler way than this?
            transport, protocol = await self._event_loop.connect_write_pipe(
                asyncio.Protocol, os.fdopen(barrier_out))
            transport.write(b'1')
            transport.close()

    #         # Wait for it to write back its server address.
    #         # TODO: need to timeout? what happens when child terminates
    #         # before full address is written?
    #         stub_address = b''
    #         while True:
    #             read = os.read(announce_in, 1024)
    #             if not read:
    #                 break
    #             stub_address += read
    #         os.close(announce_in)
    #         proc.address = stub_address.decode('utf-8')
    #         logger.info(
    #             "Child pid=%d has IPC address %s", pid, proc.address)

            return proc

    def sigchld_handler(self):
        logger.info("Received SIGCHLD.")
        self.collect_dead_children()

    def collect_dead_children(self):
        dead_children = set()
        for pid, stub in self._processes.items():
            pid, status, resinfo = os.wait4(pid, os.WNOHANG)
            if pid == 0:
                continue

            try:
                proc = self._processes[pid]
            except KeyError:
                logger.warning("Unknown child pid=%d", pid)
                continue

            if proc.state != ProcessState.RUNNING:
                proc.logger.error("Unexpected state %s", proc.state)
                continue

            if os.WIFEXITED(status):
                proc.returncode = os.WEXITSTATUS(status)
                proc.logger.info("Terminated with rc=%d", proc.returncode)
            elif os.WIFSIGNALED(status):
                proc.returncode = 1
                proc.signal = os.WTERMSIG(status)
                proc.logger.info("Terminated by signal=%d", proc.signal)
            elif os.WIFSTOPPED(status):
                sig = os.WSTOPSIG(status)
                proc.logger.info("Stopped by signal=%d", sig)
                continue
            else:
                proc.logger.error("Unexpected status %d", status)
                continue

            proc.resinfo = resinfo
            proc.logger.info("Resource usage:")
            proc.logger.info("  utime=%f", resinfo.ru_utime)
            proc.logger.info("  stime=%f", resinfo.ru_stime)
            proc.logger.info("  maxrss=%d", resinfo.ru_maxrss)
            proc.logger.info("  ixrss=%d", resinfo.ru_ixrss)
            proc.logger.info("  idrss=%d", resinfo.ru_idrss)
            proc.logger.info("  isrss=%d", resinfo.ru_isrss)
            proc.logger.info("  minflt=%d", resinfo.ru_minflt)
            proc.logger.info("  majflt=%d", resinfo.ru_majflt)
            proc.logger.info("  nswap=%d", resinfo.ru_nswap)
            proc.logger.info("  inblock=%d", resinfo.ru_inblock)
            proc.logger.info("  oublock=%d", resinfo.ru_oublock)
            proc.logger.info("  msgsnd=%d", resinfo.ru_msgsnd)
            proc.logger.info("  msgrcv=%d", resinfo.ru_msgrcv)
            proc.logger.info("  nsignals=%d", resinfo.ru_nsignals)
            proc.logger.info("  nvcsw=%d", resinfo.ru_nvcsw)
            proc.logger.info("  nivcsw=%d", resinfo.ru_nivcsw)

            proc.state = ProcessState.FINISHED
            proc.term_event.set()

            dead_children.add(pid)

        for pid in dead_children:
            del self._processes[pid]


class ProcessImpl(object):
    def __init__(self, name):
        self.name = name
        self.pid = os.getpid()

        # self.manager = ManagerStub(manager_address)
        # self.server = ipc.Server(name)

    # def main(self, ready_callback, *args, **kwargs):
        # with self.manager:
        #     with self.server:
        #         self.server.start()
        #         try:
        #             self.setup()
        #             ready_callback()

        #             self.run(*args, **kwargs)
        #         finally:
        #             self.cleanup()

    def setup(self):
        pass

    def cleanup(self):
        pass

    def run(self):
        raise NotImplementedError("Subclass must override run")


class ProcessHandle(object):
    def __init__(self):
        self.state = ProcessState.NOT_STARTED
        self.pid = None
#         self.address = None
        self.returncode = None
        self.signal = None
        self.resinfo = None
        self.term_event = asyncio.Event()
        self.logger = None
        self.stdout_logger = None
        self.stderr_logger = None

    def create_loggers(self):
        assert self.pid is not None
        self.logger = logging.getLogger('childproc[%d]' % self.pid)
        self._stdout_logger = self.logger.getChild('stdout')
        self._stderr_logger = self.logger.getChild('stderr')

    async def setup_std_handlers(self, event_loop, stdout, stderr):
        await event_loop.connect_read_pipe(
            functools.partial(PipeAdapter, self._stdout_logger.info),
            os.fdopen(stdout))

        await event_loop.connect_read_pipe(
            functools.partial(PipeAdapter, self._stderr_logger.info),
            os.fdopen(stderr))

    async def wait(self):
        await self.term_event.wait()


# class ManagerStub(ipc.Stub):
#     pass
