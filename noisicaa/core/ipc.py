#!/usr/bin/python3

import asyncio
import enum
import functools
import logging
import os
import os.path
import pickle
import tempfile
import traceback
import uuid

logger = logging.getLogger(__name__)


class RemoteException(Exception): pass
class Error(Exception): pass
class InvalidResponseError(Error): pass


class ConnState(enum.Enum):
    READ_MESSAGE = 1
    READ_PAYLOAD = 2


class ServerProtocol(asyncio.Protocol):
    def __init__(self, event_loop, server):
        self.event_loop = event_loop
        self.server = server
        self.id = server.new_connection_id()
        self.transport = None
        self.state = ConnState.READ_MESSAGE
        self.command = None
        self.payload_length = None
        self.inbuf = bytearray()
        self.logger = server.logger.getChild("conn-%d" % self.id)

    def connection_made(self, transport):
        self.logger.info("Accepted new connection.")
        self.transport = transport

    def connection_lost(self, exc):
        self.logger.info("Connection closed.")

    def data_received(self, data):
        self.inbuf.extend(data)

        while self.inbuf:
            if self.state == ConnState.READ_MESSAGE:
                try:
                    eol = self.inbuf.index(b'\n')
                except ValueError:
                    break

                header = bytes(self.inbuf[:eol])
                self.inbuf = self.inbuf[eol+1:]
                if header == b'PING':
                    self.logger.info("PING received")
                    self.transport.write(b'ACK 4\nPONG')

                elif header.startswith(b'CALL '):
                    command, length = header[5:].split(b' ')
                    self.command = command.decode('ascii')
                    self.payload_length = int(length)
                    self.logger.info("CALL %s received (%d bytes payload)", self.command, self.payload_length)
                    if self.payload_length > 0:
                        self.state = ConnState.READ_PAYLOAD
                    else:
                        task = self.event_loop(
                            self.server.handle_command(
                                self.command, None))
                        task.add_done_callback(self.command_complete)
                else:
                    self.logger.error("Received unknown message '%s'", header)
            elif self.state == ConnState.READ_PAYLOAD:
                if len(self.inbuf) < self.payload_length:
                    break
                payload = bytes(self.inbuf[:self.payload_length])
                del self.inbuf[:self.payload_length]
                self.logger.debug("payload: %s", payload)
                task = self.event_loop.create_task(
                    self.server.handle_command(self.command, payload))
                task.add_done_callback(self.command_complete)
                self.state = ConnState.READ_MESSAGE
                self.command = None
                self.payload_length = None

    def command_complete(self, task):
        if task.exception() is not None:
            raise task.exception()

        response = task.result() or b''
        self.transport.write(b'ACK %d\n' % len(response))
        if response:
            self.transport.write(response)


class Server(object):
    serialize = functools.partial(
        pickle.dumps, protocol=pickle.HIGHEST_PROTOCOL)
    deserialize = pickle.loads

    def __init__(self, event_loop, name, socket_dir=None):
        self.event_loop = event_loop
        self.name = name

        self.logger = logger.getChild(name)

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, '%s.%s.sock' % (self.name, uuid.uuid4().hex))

        self._next_connection_id = 0
        self._server = None

        self._command_handlers = {}

    def add_command_handler(self, cmd, handler):
        assert cmd not in self._command_handlers
        self._command_handlers[cmd] = handler

    def new_connection_id(self):
        self._next_connection_id += 1
        return self._next_connection_id

    async def setup(self):
        self._server = await self.event_loop.create_unix_server(
            functools.partial(ServerProtocol, self.event_loop, self),
            path=self.address)
        self.logger.info("Listening on socket %s", self.address)

    async def cleanup(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            os.unlink(self.address)
            self._server = None
            self.logger.info("Server closed")

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        return False

    # def send_close(self):
    #     sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    #     sock.connect(self.address)
    #     sock.sendall(b'CLOSE\n')
    #     sock.close()

    # def wait_for_pending_connections(self):
    #     while len(self._connections) > 0:
    #         time.sleep(0.01)

    async def handle_command(self, command, payload):
        try:
            handler = self._command_handlers[command]

            args, kwargs = self.deserialize(payload)
            if asyncio.iscoroutinefunction(handler):
                result = await handler(*args, **kwargs)
            else:
                result = handler(*args, **kwargs)
            if result is not None:
                return b'OK:' + self.serialize(result)
            else:
                return b'OK'
        except Exception as exc:  # pylint: disable=broad-except
            return b'EXC:' + str(traceback.format_exc()).encode('utf-8')


class ClientProtocol(asyncio.Protocol):
    def __init__(self, stub):
        self.stub = stub
        self.closed_event = asyncio.Event()
        self.state = 0
        self.buf = bytearray()
        self.length = None
        self.response = None
        self.response_queue = asyncio.Queue()

    def connection_lost(self, exc):
        self.closed_event.set()

    def data_received(self, data):
        self.buf.extend(data)

        while self.buf:
            if self.state == 0:
                eol = self.buf.find(b'\n')
                if eol == -1:
                    break
                ack, length = self.buf[:eol].split(b' ')
                self.length = int(length)
                self.response = None
                del self.buf[:eol+1]
                assert ack == b'ACK'
                if self.length > 0:
                    self.state = 1
                else:
                    self.response_queue.put_nowait(self.response)
                    self.state = 0

            elif self.state == 1:
                if len(self.buf) < self.length:
                    break
                self.response = bytes(self.buf[:self.length])
                del self.buf[:self.length]
                self.response_queue.put_nowait(self.response)
                self.state = 0

            else:
                raise RuntimeError("Invalid state %d" % self.state)


class Stub(object):
    serialize = functools.partial(
        pickle.dumps, protocol=pickle.HIGHEST_PROTOCOL)
    deserialize = pickle.loads

    def __init__(self, event_loop, server_address):
        self._event_loop = event_loop
        self._server_address = server_address
        self._transport = None
        self._protocol = None

    @property
    def connected(self):
        return self._transport is not None

    async def connect(self):
        assert self._transport is None and self._protocol is None
        self._transport, self._protocol = (
            await self._event_loop.create_unix_connection(
                functools.partial(ClientProtocol, self),
                self._server_address))
        logger.info("Connected to server at %s", self._server_address)

    async def close(self):
        assert self._transport is not None
        self._transport.close()
        await self._protocol.closed_event.wait()

        self._transport = None
        self._protocol = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def call(self, cmd, *args, **kwargs):
        if not isinstance(cmd, bytes):
            cmd = cmd.encode('ascii')
        payload = self.serialize([args, kwargs])
        self._transport.write(b'CALL %s %d\n' % (cmd, len(payload)))
        if payload:
            self._transport.write(payload)

        response = await self._protocol.response_queue.get()

        if response == b'OK':
            return None
        elif response.startswith(b'OK:'):
            return self.deserialize(response[3:])
        elif response.startswith(b'EXC:'):
            raise RemoteException(response[4:].decode('utf-8'))
        else:
            raise InvalidResponseError(response)

    def call_sync(self, cmd, payload=b''):
        return self._event_loop.run_until_complete(self.call(cmd, payload))

    async def ping(self):
        self._transport.write(b'PING\n')
        response = await self._protocol.response_queue.get()
        assert response == b'PONG', response
