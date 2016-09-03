#!/usr/bin/python3

import asyncio
import enum
import functools
import importlib
import logging
import os
import pickle
import signal
import struct
import sys
import time
import traceback

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


class LogAdapter(asyncio.Protocol):
    def __init__(self, logger):
        super().__init__()
        self._logger = logger
        self._buf = bytearray()
        self._state = 'header'
        self._length = None

    def data_received(self, data):
        self._buf.extend(data)
        while True:
            if self._state == 'header':
                if len(self._buf) < 6:
                    break
                header = self._buf[:6]
                del self._buf[:6]
                assert header == b'RECORD'
                self._state = 'length'
            elif self._state == 'length':
                if len(self._buf) < 4:
                    break
                packed_length = self._buf[:4]
                del self._buf[:4]
                self._length, = struct.unpack('>L', packed_length)
                self._state = 'record'
            elif self._state == 'record':
                if len(self._buf) < self._length:
                    break
                serialized_record = self._buf[:self._length]
                del self._buf[:self._length]

                record_attr = pickle.loads(serialized_record)
                record = logging.makeLogRecord(record_attr)
                self._logger.handle(record)

                self._state = 'header'

class ChildLogHandler(logging.Handler):
    def __init__(self, log_fd):
        super().__init__()
        self._log_fd = log_fd

    def handle(self, record):
        record_attrs = {
            'msg': record.getMessage(),
            'args': (),
        }
        for attr in (
                'created', 'exc_text', 'filename',
                'funcName', 'levelname', 'levelno', 'lineno',
                'module', 'msecs', 'name', 'pathname', 'process',
                'relativeCreated', 'thread', 'threadName'):
            record_attrs[attr] = record.__dict__[attr]

        serialized_record = pickle.dumps(record_attrs)
        msg = bytearray()
        msg += b'RECORD'
        msg += struct.pack('>L', len(serialized_record))
        msg += serialized_record

        while msg:
            written = os.write(self._log_fd, msg)
            msg = msg[written:]


class ProcessManager(object):
    def __init__(self, event_loop):
        self._event_loop = event_loop
        self._processes = {}
        self._sigchld_received = asyncio.Event()

        self._server = ipc.Server(event_loop, 'manager')

    @property
    def server(self):
        return self._server

    async def setup(self):
        logger.info("Starting ProcessManager...")
        self._event_loop.add_signal_handler(
            signal.SIGCHLD, self.sigchld_handler)

        await self._server.setup()

    async def cleanup(self):
        await self.terminate_all_children()
        await self._server.cleanup()

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        return False

    async def terminate_all_children(self, timeout=10):
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
                try:
                    await asyncio.wait_for(
                        self._sigchld_received.wait(), min(0.05, timeout))
                    self._sigchld_received.clear()
                except asyncio.TimeoutError:
                    pass

        for pid in self._processes.keys():
            logger.error("Failed to kill child pid=%d", pid)

    async def start_process(self, name, cls, **kwargs):
        proc = ProcessHandle()

        barrier_in, barrier_out = os.pipe()
        announce_in, announce_out = os.pipe()
        stdout_in, stdout_out = os.pipe()
        stderr_in, stderr_out = os.pipe()
        logger_in, logger_out = os.pipe()

        manager_address = self._server.address

        pid = os.fork()
        if pid == 0:
            # In child process.
            try:
                # Remove all signal handlers.
                for sig in signal.Signals:
                    self._event_loop.remove_signal_handler(sig)

                # Close the "other ends" of the pipes.
                os.close(barrier_out)
                os.close(announce_in)
                os.close(stdout_in)
                os.close(stderr_in)
                os.close(logger_in)

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

                # Remove all existing log handlers, and install a new
                # handler to pipe all log messages back to the manager
                # process.
                root_logger = logging.getLogger()
                while root_logger.handlers:
                    root_logger.removeHandler(root_logger.handlers[0])
                root_logger.addHandler(ChildLogHandler(logger_out))

                if isinstance(cls, str):
                    mod_name, cls_name = cls.rsplit('.', 1)
                    mod = importlib.import_module(mod_name)
                    cls = getattr(mod, cls_name)
                impl = cls(
                    name=name, manager_address=manager_address, **kwargs)

                # TODO: if crashes before ready_callback was sent, write
                # back failure message to pipe.
                def ready_callback():
                    stub_address = impl.server.address.encode('utf-8')
                    while stub_address:
                        written = os.write(announce_out, stub_address)
                        stub_address = stub_address[written:]
                    os.close(announce_out)

                rc = impl.main(ready_callback)

            except SystemExit as exc:
                rc = exc.code
            except:  # pylint: disable=bare-except
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
            os.close(stdout_out)
            os.close(stderr_out)
            os.close(logger_out)

            self._processes[pid] = proc

            proc.pid = pid
            proc.create_loggers()

            proc.logger.info("Created new subprocess.")

            await proc.setup_std_handlers(
                self._event_loop, stdout_in, stderr_in, logger_in)

            # Unleash the child.
            proc.state = ProcessState.RUNNING

            # TODO: There's no simpler way than this?
            transport, _ = await self._event_loop.connect_write_pipe(
                asyncio.Protocol, os.fdopen(barrier_out))
            transport.write(b'1')
            transport.close()  # Does this close the FD?

            # Wait for it to write back its server address.
            # TODO: need to timeout? what happens when child terminates
            # before full address is written?
            reader = asyncio.StreamReader(loop=self._event_loop)
            transport, protocol = await self._event_loop.connect_read_pipe(
                functools.partial(
                    asyncio.StreamReaderProtocol,
                    reader, loop=self._event_loop),
                os.fdopen(announce_in))
            stub_address = await reader.read()
            transport.close()  # Does this close the FD?

            proc.address = stub_address.decode('utf-8')
            logger.info(
                "Child pid=%d has IPC address %s", pid, proc.address)

            return proc

    def sigchld_handler(self):
        logger.info("Received SIGCHLD.")
        self.collect_dead_children()
        self._sigchld_received.set()

    def collect_dead_children(self):
        dead_children = set()
        for pid, proc in self._processes.items():
            rpid, status, resinfo = os.wait4(pid, os.WNOHANG)
            if rpid == 0:
                continue
            assert rpid == pid

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

            # The handle should receive an EOF when the child died and the
            # pipe gets closed. We should wait for it asynchronously.
            proc.stdout_protocol.eof_received()
            proc.stderr_protocol.eof_received()

            proc.resinfo = resinfo
            # proc.logger.info("Resource usage:")
            # proc.logger.info("  utime=%f", resinfo.ru_utime)
            # proc.logger.info("  stime=%f", resinfo.ru_stime)
            # proc.logger.info("  maxrss=%d", resinfo.ru_maxrss)
            # proc.logger.info("  ixrss=%d", resinfo.ru_ixrss)
            # proc.logger.info("  idrss=%d", resinfo.ru_idrss)
            # proc.logger.info("  isrss=%d", resinfo.ru_isrss)
            # proc.logger.info("  minflt=%d", resinfo.ru_minflt)
            # proc.logger.info("  majflt=%d", resinfo.ru_majflt)
            # proc.logger.info("  nswap=%d", resinfo.ru_nswap)
            # proc.logger.info("  inblock=%d", resinfo.ru_inblock)
            # proc.logger.info("  oublock=%d", resinfo.ru_oublock)
            # proc.logger.info("  msgsnd=%d", resinfo.ru_msgsnd)
            # proc.logger.info("  msgrcv=%d", resinfo.ru_msgrcv)
            # proc.logger.info("  nsignals=%d", resinfo.ru_nsignals)
            # proc.logger.info("  nvcsw=%d", resinfo.ru_nvcsw)
            # proc.logger.info("  nivcsw=%d", resinfo.ru_nivcsw)

            proc.state = ProcessState.FINISHED
            proc.term_event.set()

            dead_children.add(pid)

        for pid in dead_children:
            del self._processes[pid]


class ProcessImpl(object):
    def __init__(self, name, manager_address):
        self.name = name
        self.manager_address = manager_address
        self.event_loop = None
        self.pid = os.getpid()

        self.manager = None
        self.server = None

    def create_event_loop(self):
        return asyncio.new_event_loop()

    def main(self, ready_callback, *args, **kwargs):
        # Create a new event loop to replace the one we inherited.
        self.event_loop = self.create_event_loop()
        asyncio.set_event_loop(self.event_loop)

        try:
            return self.event_loop.run_until_complete(
                self.main_async(ready_callback, *args, **kwargs))
        finally:
            self.event_loop.stop()
            self.event_loop.close()

    async def main_async(self, ready_callback, *args, **kwargs):
        self.manager = ManagerStub(self.event_loop, self.manager_address)
        async with self.manager:
            self.server = ipc.Server(self.event_loop, self.name)
            async with self.server:
                try:
                    logger.info("Setting up process.")
                    await self.setup()
                    ready_callback()

                    logger.info("Entering run method.")
                    return await self.run(*args, **kwargs)
                except Exception as exc:
                    logger.error(
                        "Unhandled exception in process %s:\n%s",
                        self.name, traceback.format_exc())
                    raise
                finally:
                    await self.cleanup()

    async def setup(self):
        pass

    async def cleanup(self):
        pass

    async def run(self):
        raise NotImplementedError("Subclass must override run")


class SetPIDHandler(logging.Handler):
    def __init__(self, pid):
        super().__init__()
        self._pid = pid

    def handle(self, record):
        record.process = self._pid


class ProcessHandle(object):
    def __init__(self):
        self.state = ProcessState.NOT_STARTED
        self.pid = None
        self.address = None
        self.returncode = None
        self.signal = None
        self.resinfo = None
        self.term_event = asyncio.Event()
        self.logger = None
        self.stdout_logger = None
        self.stderr_logger = None
        self.stdout_protocol = None
        self.stderr_protocol = None
        self.logger_protocol = None

        self._stderr_empty_lines = []

    def create_loggers(self):
        assert self.pid is not None
        self.logger = logging.getLogger('childproc[%d]' % self.pid)

        self.stdout_logger = self.logger.getChild('stdout')
        self.stdout_logger.addHandler(SetPIDHandler(self.pid))
        self.stderr_logger = self.logger.getChild('stderr')
        self.stderr_logger.addHandler(SetPIDHandler(self.pid))

    async def setup_std_handlers(
        self, event_loop, stdout_fd, stderr_fd, logger_fd):
        _, self.stdout_protocol = await event_loop.connect_read_pipe(
            functools.partial(PipeAdapter, self.handle_stdout),
            os.fdopen(stdout_fd))

        _, self.stderr_protocol = await event_loop.connect_read_pipe(
            functools.partial(PipeAdapter, self.handle_stderr),
            os.fdopen(stderr_fd))

        _, self.logger_protocol = await event_loop.connect_read_pipe(
            functools.partial(LogAdapter, self.logger),
            os.fdopen(logger_fd))

    async def wait(self):
        await self.term_event.wait()

    def handle_stdout(self, line):
        self.stdout_logger.info(line)

    def handle_stderr(self, line):
        if len(line.rstrip('\r\n')) == 0:
            # Buffer empty lines, so we can discard those that are followed
            # by a message that we also want to discard.
            self._stderr_empty_lines.append(line)
            return

        if 'fluid_synth_sfont_unref' in line:
            # Discard annoying error message from libfluidsynth. It is also
            # preceeded by a empty line, which we also throw away.
            self._stderr_empty_lines.clear()
            return

        while len(self._stderr_empty_lines) > 0:
            self.stderr_logger.warning(self._stderr_empty_lines.pop(0))
        self.stderr_logger.warning(line)


class ManagerStub(ipc.Stub):
    pass
