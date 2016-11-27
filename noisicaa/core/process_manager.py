#!/usr/bin/python3

import asyncio
import enum
import functools
import importlib
import logging
import os
import pickle
import pprint
import select
import signal
import struct
import sys
import threading
import time
import traceback

import eventfd

from . import ipc
from . import stats

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


class ChildConnection(object):
    def __init__(self, fd_in, fd_out):
        self.fd_in = fd_in
        self.fd_out = fd_out

        self.__reader_state = 0
        self.__reader_buf = None
        self.__reader_length = None

    def write(self, request):
        assert isinstance(request, bytes)
        header = b'#%d\n' % len(request)
        msg = header + request
        while msg:
            written = os.write(self.fd_out, msg)
            msg = msg[written:]

    def __reader_start(self):
        self.__reader_state = 0
        self.__reader_buf = None
        self.__reader_length = None

    def __read_internal(self):
        if self.__reader_state == 0:
            d = os.read(self.fd_in, 1)
            assert d == b'#'
            self.__reader_buf = bytearray()
            self.__reader_state = 1

        elif self.__reader_state == 1:
            d = os.read(self.fd_in, 1)
            if d == b'\n':
                self.__reader_length = int(self.__reader_buf)
                self.__reader_buf = bytearray()
                self.__reader_state = 2
            else:
                self.__reader_buf += d

        elif self.__reader_state == 2:
            if len(self.__reader_buf) < self.__reader_length:
                d = os.read(self.fd_in, self.__reader_length - len(self.__reader_buf))
                self.__reader_buf += d

            if len(self.__reader_buf) == self.__reader_length:
                self.__reader_state = 3

    @property
    def __reader_done(self):
        return self.__reader_state == 3

    @property
    def __reader_response(self):
        assert self.__reader_done
        return self.__reader_buf

    def read(self):
        self.__reader_start()
        while not self.__reader_done:
            self.__read_internal()
        return self.__reader_response

    async def read_async(self, event_loop):
        done = asyncio.Event(loop=event_loop)
        def read_cb():
            try:
                self.__read_internal()
            except:
                event_loop.remove_reader(self.fd_in)
                raise
            if self.__reader_done:
                event_loop.remove_reader(self.fd_in)
                done.set()

        self.__reader_start()
        event_loop.add_reader(self.fd_in, read_cb)
        await done.wait()

        return self.__reader_response

    def close(self):
        os.close(self.fd_in)
        os.close(self.fd_out)


class ChildCollector(object):
    def __init__(self, stats_collector, collection_interval=100):
        self.__stats_collector = stats_collector
        self.__collection_interval = collection_interval

        self.__stat_poll_duration = None
        self.__stat_poll_count = None

        self.__lock = threading.Lock()
        self.__connections = {}
        self.__stop = None
        self.__thread = None

    def setup(self):
        self.__stat_poll_duration = stats.registry.register(
            stats.Counter, stats.StatName(name='stat_collector_duration_total'))
        self.__stat_poll_count = stats.registry.register(
            stats.Counter, stats.StatName(name='stat_collector_collections'))

        self.__stop = threading.Event()
        self.__thread = threading.Thread(target=self.__main)
        self.__thread.start()

    def cleanup(self):
        if self.__thread is not None:
            self.__stop.set()
            self.__thread.join()
            self.__thread = None
            self.__stop = None

        for connection in self.__connections.values():
            connection.close()
        self.__connections.clear()

        if self.__stat_poll_duration is not None:
            self.__stat_poll_duration.unregister()
            self.__stat_poll_duration = None

        if self.__stat_poll_count is not None:
            self.__stat_poll_count.unregister()
            self.__stat_poll_count = None

    def add_child(self, pid, connection):
        with self.__lock:
            self.__connections[pid] = connection

    def remove_child(self, pid):
        with self.__lock:
            connection = self.__connections.pop(pid, None)
            if connection is not None:
                connection.close()

    def collect(self):
        with self.__lock:
            poll_start = time.perf_counter()

            pending = {}
            poller = select.poll()
            for pid, connection in self.__connections.items():
                t0 = time.perf_counter()
                connection.write(b'COLLECT_STATS')
                pending[connection.fd_in] = (t0, pid, connection)
                poller.register(connection.fd_in)

            while pending:
                for fd, evt in poller.poll():
                    t0, pid, connection = pending[fd]
                    if evt & select.POLLIN:
                        response = connection.read()
                        latency = time.perf_counter() - t0

                        child_name = stats.StatName(pid=pid)
                        for name, value in pickle.loads(response):
                            self.__stats_collector.add_value(
                                name.merge(child_name), value)

                        poller.unregister(fd)
                        del pending[fd]

                    elif evt & select.POLLHUP:
                        poller.unregister(fd)
                        del pending[fd]

            poll_duration = time.perf_counter() - poll_start
            self.__stat_poll_duration.incr(poll_duration)
            self.__stat_poll_count.incr(1)

        manager_name = stats.StatName(pid=os.getpid())
        for name, value in stats.registry.collect():
            self.__stats_collector.add_value(
                name.merge(manager_name), value)

    def __main(self):
        next_collection = time.perf_counter()
        while not self.__stop.is_set():
            delay = next_collection - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

            self.collect()
            next_collection += self.__collection_interval / 1e3


class ProcessManager(object):
    def __init__(self, event_loop):
        self._event_loop = event_loop
        self._processes = {}
        self._sigchld_received = asyncio.Event()

        self._server = ipc.Server(event_loop, 'manager')
        self._stats_collector = stats.Collector()
        self._child_collector = ChildCollector(
            self._stats_collector)

    @property
    def server(self):
        return self._server

    async def setup(self):
        logger.info("Starting ProcessManager...")
        self._event_loop.add_signal_handler(
            signal.SIGCHLD, self.sigchld_handler)

        self._server.add_command_handler(
            'STATS_LIST', self.handle_stats_list)
        self._server.add_command_handler(
            'STATS_FETCH', self.handle_stats_fetch)

        await self._server.setup()
        self._child_collector.setup()

    async def cleanup(self):
        self._child_collector.cleanup()

        await self.terminate_all_children()
        await self._server.cleanup()

        self._server.remove_command_handler('STATS_LIST')
        self._server.remove_command_handler('STATS_FETCH')

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

        request_in, request_out = os.pipe()
        response_in, response_out = os.pipe()
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

                # Clear all stats inherited from the manager process.
                stats.registry.clear()

                # Close the "other ends" of the pipes.
                os.close(request_out)
                os.close(response_in)
                os.close(stdout_in)
                os.close(stderr_in)
                os.close(logger_in)

                # Use the pipes as out STDIN/-ERR.
                os.dup2(stdout_out, 1)
                os.dup2(stderr_out, 2)
                os.close(stdout_out)
                os.close(stderr_out)

                # TODO: ensure that sys.stdout/err use utf-8

                child_connection = ChildConnection(request_in, response_out)

                # Wait until manager told us it's ok to start. Avoid race
                # condition where child terminates and generates SIGCHLD
                # before manager has added it to its process map.
                msg = child_connection.read()
                assert msg == b'START'

                # Remove all existing log handlers, and install a new
                # handler to pipe all log messages back to the manager
                # process.
                root_logger = logging.getLogger()
                while root_logger.handlers:
                    root_logger.removeHandler(root_logger.handlers[0])
                root_logger.addHandler(ChildLogHandler(logger_out))
                #root_logger.addHandler(logging.StreamHandler())

                if isinstance(cls, str):
                    mod_name, cls_name = cls.rsplit('.', 1)
                    mod = importlib.import_module(mod_name)
                    cls = getattr(mod, cls_name)
                impl = cls(
                    name=name, manager_address=manager_address, **kwargs)

                rc = impl.main(child_connection)

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
            os.close(request_in)
            os.close(response_out)
            os.close(stdout_out)
            os.close(stderr_out)
            os.close(logger_out)

            self._processes[pid] = proc

            child_connection = ChildConnection(response_in, request_out)

            proc.pid = pid
            proc.create_loggers()

            proc.logger.info("Created new subprocess.")

            await proc.setup_std_handlers(
                self._event_loop, stdout_in, stderr_in, logger_in)

            # Unleash the child.
            proc.state = ProcessState.RUNNING
            child_connection.write(b'START')

            stub_address = await child_connection.read_async(self._event_loop)

            self._child_collector.add_child(pid, child_connection)

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
            self._child_collector.remove_child(pid)
            del self._processes[pid]

    def handle_stats_list(self):
        return self._stats_collector.list_stats()

    def handle_stats_fetch(self, expressions):
        return self._stats_collector.fetch_stats(expressions)


class ChildConnectionHandler(object):
    def __init__(self, connection):
        self.connection = connection

        self.__stop = None
        self.__thread = None

    def setup(self):
        self.__stop = eventfd.EventFD()
        self.__thread = threading.Thread(target=self.__main)
        self.__thread.start()

    def cleanup(self):
        if self.__thread is not None:
            logger.info("Stopping ChildConnectionHandler...")
            self.__stop.set()
            self.__thread.join()
            self.__thread = None
            self.__stop = None

    def __main(self):
        fd_in = self.connection.fd_in

        poller = select.poll()
        poller.register(fd_in, select.POLLIN | select.POLLHUP)
        poller.register(self.__stop, select.POLLIN)
        while not self.__stop.is_set():
            for fd, evt in poller.poll():
                if fd == fd_in and evt & select.POLLIN:
                    request = self.connection.read()
                    if request == b'COLLECT_STATS':
                        data = stats.registry.collect()
                        response = pickle.dumps(data, protocol=-1)
                    else:
                        raise ValueError(request)

                    try:
                        self.connection.write(response)
                    except BrokenPipeError:
                        logger.warning("Failed to write COLLECT_STATS response.")

                elif fd == fd_in and evt & select.POLLHUP:
                    logger.warning("Child connection closed.")
                    poller.unregister(fd_in)

        logger.info("ChildConnectionHandler stopped.")


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

    def error_handler(self, event_loop, context):
        event_loop.default_exception_handler(context)
        logging.error("%s:\n%s", context['message'], traceback.format_exc())
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    def main(self, child_connection, *args, **kwargs):
        # Create a new event loop to replace the one we inherited.
        self.event_loop = self.create_event_loop()
        self.event_loop.set_exception_handler(self.error_handler)
        asyncio.set_event_loop(self.event_loop)

        try:
            return self.event_loop.run_until_complete(
                self.main_async(child_connection, *args, **kwargs))
        finally:
            self.event_loop.stop()
            self.event_loop.close()

    async def main_async(self, child_connection, *args, **kwargs):
        self.manager = ManagerStub(self.event_loop, self.manager_address)
        async with self.manager:
            self.server = ipc.Server(self.event_loop, self.name)
            async with self.server:
                try:
                    logger.info("Setting up process.")
                    await self.setup()

                    stub_address = self.server.address.encode('utf-8')
                    child_connection.write(stub_address)

                    child_connection_handler = ChildConnectionHandler(child_connection)
                    child_connection_handler.setup()
                    try:
                        logger.info("Entering run method.")
                        return await self.run(*args, **kwargs)

                    except Exception as exc:
                        logger.error(
                            "Unhandled exception in process %s:\n%s",
                            self.name, traceback.format_exc())
                        raise

                    finally:
                        child_connection_handler.cleanup()
                        child_connection.close()

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
