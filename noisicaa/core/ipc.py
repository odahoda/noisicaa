#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import asyncio
import enum
import functools
import io
import logging
import os
import os.path
import random
import struct
import time
import traceback
from typing import (
    cast, Any, Optional, Union, Dict, List, Set, Callable, Awaitable, Coroutine, Sequence, Type,
    Generic, TypeVar)
import urllib.parse
import uuid

from google.protobuf import message as protobuf

from . import stats
from . import ipc_pb2

logger = logging.getLogger(__name__)


class RemoteException(Exception):
    def __init__(self, server_address: str, tb: str) -> None:
        super().__init__("From server %s:\n%s" % (server_address, tb))

class CloseConnection(Exception):
    pass

class Error(Exception):
    pass

class ConnectionFailedError(Error):
    pass

class ConnectionClosed(Error):
    pass


frame_header = struct.Struct('=L?')
request_header = struct.Struct('=Qc')


class ConnState(enum.Enum):
    READ_HEADER = 1
    READ_DATA = 2


class FrameProtocol(asyncio.Protocol):
    def __init__(
            self,
            logger: logging.Logger,  # pylint: disable=redefined-outer-name
    ) -> None:
        super().__init__()

        self.logger = logger

        self.transport = None  # type: asyncio.WriteTransport

        self.state = ConnState.READ_HEADER
        self.frames = []  # type: List[bytes]
        self.frame_size = None
        self.more = None
        self.inbuf = bytearray()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast(asyncio.WriteTransport, transport)

    def data_received(self, data: bytes) -> None:
        self.inbuf.extend(data)

        while self.inbuf:
            if self.state == ConnState.READ_HEADER:
                if len(self.inbuf) < frame_header.size:
                    break

                self.frame_size, self.more = frame_header.unpack_from(self.inbuf)
                del self.inbuf[:frame_header.size]
                if self.frame_size == 0:
                    self.frames.append(b'')
                    if not self.more:
                        self.handle_message(self.frames)
                        self.frames = []

                else:
                    self.state = ConnState.READ_DATA

            elif self.state == ConnState.READ_DATA:
                if len(self.inbuf) < self.frame_size:
                    break
                frame = bytes(self.inbuf[:self.frame_size])
                del self.inbuf[:self.frame_size]

                self.frames.append(frame)
                if not self.more:
                    self.handle_message(self.frames)
                    self.frames = []

                self.frame_size = None
                self.more = None
                self.state = ConnState.READ_HEADER

    def handle_message(self, frame: List[bytes]) -> None:
        raise NotImplementedError


class Session(object):
    def __init__(
            self,
            session_id: int,
            start_session_request: ipc_pb2.StartSessionRequest,
            event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.__id = session_id
        self.__closed = False
        self._event_loop = event_loop

    @property
    def id(self) -> int:
        return self.__id

    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    @property
    def closed(self) -> bool:
        # TODO: should trigger CallbackSessionMixin.session_ended()
        return self.__closed

    def close(self) -> None:
        logger.info("Session %016x closed.", self.id)
        self.__closed = True


class CallbackSessionMixin(Session):
    async_connect = True

    def __init__(
            self,
            session_id: int,
            start_session_request: ipc_pb2.StartSessionRequest,
            event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(session_id, start_session_request, event_loop)

        assert start_session_request.HasField('callback_address')
        self.__callback_address = start_session_request.callback_address
        self.__connect_task = None  # type: asyncio.Task
        self.__callback_stub = None  # type: Stub

    @property
    def callback_alive(self) -> bool:
        return (
            not self.closed
            and self.__callback_stub is not None
            and self.__callback_stub.connected)

    async def setup(self) -> None:
        await super().setup()

        self.__callback_stub = Stub(self._event_loop, self.__callback_address)
        if self.async_connect:
            self.__connect_task = self._event_loop.create_task(self.__callback_stub.connect())
            self.__connect_task.add_done_callback(self.__callback_connected)
        else:
            self.__connect_task = await self.__callback_stub.connect()

    def __callback_connected(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return

        assert task.done()
        exc = task.exception()
        if exc is not None:
            logger.error("Session %016x: Failed to connect to callback client: %s", self.id, exc)
            self.close()
            return

        assert self.__callback_stub.connected
        self.callback_connected()

    async def cleanup(self) -> None:
        if self.__connect_task is not None:
            self.__connect_task.cancel()
            self.__connect_task = None

        if self.__callback_stub is not None:
            await self.__callback_stub.close()
            self.__callback_stub = None

    def callback_connected(self) -> None:
        pass

    async def callback(self, cmd: str, request: protobuf.Message = None) -> None:
        assert self.callback_alive
        await self.__callback_stub.call(cmd, request)

    def async_callback(self, cmd: str, request: protobuf.Message = None) -> None:
        assert self.callback_alive

        callback_task = self._event_loop.create_task(
            self.__callback_stub.call(cmd, request))
        callback_task.add_done_callback(
            functools.partial(self.__callback_done, cmd))

    def __callback_done(self, cmd: str, task: asyncio.Task) -> None:
        if task.cancelled():
            logger.info("Session %016x: %s was cancelled.", self.id, cmd)
            return

        exc = task.exception()
        if isinstance(exc, ConnectionClosed):
            logger.warning("Session %016x: callback connection closed.", self.id)
            self.close()

        elif exc is not None:
            buf = io.StringIO()
            task.print_stack(file=buf)
            logger.error(
                "Session %016x: %s failed with exception: %s\n%s",
                self.id, cmd, exc, buf.getvalue())
            self.close()


class ServerProtocol(FrameProtocol):
    def __init__(self, server: 'Server') -> None:
        super().__init__(server.logger)
        self.__server = server
        self.__id = random.getrandbits(63)
        self.__active_requests = set()  # type: Set[int]
        self.__drain = False
        self.__closed = asyncio.Event(loop=server.event_loop)
        self.__endpoint = None  # type: BaseServerEndpoint
        self.__session = None  # type: Session

    @property
    def id(self) -> int:
        return self.__id

    async def wait_closed(self) -> None:
        await self.__closed.wait()

    def drain(self) -> None:
        self.__drain = True
        if not self.__active_requests:
            self.transport.close()
        self.logger.info(
            "%s: Draining connection with %d active requests",
            self.__server.id, len(self.__active_requests))

    def send_frames(self, frames: Sequence[bytes]) -> None:
        last_idx = len(frames) - 1
        for idx, frame in enumerate(frames):
            self.transport.write(frame_header.pack(len(frame), idx != last_idx))
            self.transport.write(frame)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        super().connection_made(transport)
        self.logger.info("%s: Accepted new connection.", self.__server.id)
        self.__server.add_connection(self)

    def connection_lost(self, exc: Exception) -> None:
        super().connection_lost(exc)
        self.logger.info("%s: Connection closed.", self.__server.id)
        if self.__session is not None:
            assert isinstance(self.__endpoint, ServerEndpointWithSessions)
            self.__server.event_loop.create_task(
                self.__endpoint.delete_session(self.__session.id))
        self.__server.remove_connection(self)
        self.__closed.set()

    def handle_message(self, frames: List[bytes]) -> None:
        if self.__drain:
            self.send_frames([frames[0], b'CLOSED'])
            return

        request_id, request_type = request_header.unpack(frames[0])
        if request_type == b'C':
            try:
                assert self.__endpoint is not None
                assert len(frames) == 3
                handler = self.__endpoint.get_handler(frames[1])

            except Exception:  # pylint: disable=broad-except
                self.send_frames(
                    [frames[0], b'EXC', str(traceback.format_exc()).encode('utf-8')])

            else:
                self.__active_requests.add(request_id)
                task = self.__server.event_loop.create_task(handler.run(frames[2], self.__session))
                task.add_done_callback(functools.partial(self.send_response, frames[0]))

        elif request_type == b'S':
            response_frames = None
            try:
                assert self.__endpoint is None
                endpoint = self.__server.get_endpoint(frames[1])
                if isinstance(endpoint, ServerEndpointWithSessions):
                    start_session_request = ipc_pb2.StartSessionRequest()
                    if len(frames) == 3:
                        start_session_request.ParseFromString(frames[2])
                    self.__server.event_loop.create_task(
                        self.__start_session(frames[0], endpoint, start_session_request))
                else:
                    assert len(frames) == 2
                    response_frames = [frames[0], b'OK', b'']

                self.__endpoint = endpoint

            except Exception:  # pylint: disable=broad-except
                self.send_frames([frames[0], b'EXC', str(traceback.format_exc()).encode('utf-8')])

            else:
                if response_frames:
                    self.send_frames(response_frames)

        elif request_type == b'P':
            self.send_frames([frames[0], b'PONG'])

        else:
            raise ValueError(request_type)

    async def __start_session(
            self,
            header: bytes,
            endpoint: 'ServerEndpointWithSessions',
            start_session_request: ipc_pb2.StartSessionRequest
    ) -> None:
        self.__session = await endpoint.create_session(
            self.__id, start_session_request, self.__server.event_loop)
        self.send_frames([header, b'OK', struct.pack('=Q', self.__session.id)])

    def send_response(self, header: bytes, task: asyncio.Task) -> None:
        try:
            result_frames = task.result()
        except CloseConnection:
            self.transport.close()
        else:
            self.send_frames([header] + result_frames)

            request_id, _ = request_header.unpack(header)
            self.__active_requests.remove(request_id)
            if self.__drain and not self.__active_requests:
                self.transport.close()


class CommandHandler(object):
    def __init__(
            self,
            command: bytes,
            handler: Callable,
            request_cls: Type[protobuf.Message],
            response_cls: Type[protobuf.Message],
    ) -> None:
        self.command = command
        self.handler = handler
        self.request_cls = request_cls
        self.response_cls = response_cls

    async def run(self, payload: bytes, session: Optional[Session]) -> List[bytes]:
        try:
            request = self.request_cls()
            if len(payload) > 0:
                request.ParseFromString(payload)
            response = self.response_cls()

            if session is not None:
                if asyncio.iscoroutinefunction(self.handler):
                    await self.handler(session, request, response)
                else:
                    self.handler(session, request, response)
            else:
                if asyncio.iscoroutinefunction(self.handler):
                    await self.handler(request, response)
                else:
                    self.handler(request, response)

            return [b'OK', response.SerializeToString()]

        except CloseConnection:
            raise

        except Exception:  # pylint: disable=broad-except
            return [b'EXC', str(traceback.format_exc()).encode('utf-8')]


class BaseServerEndpoint(object):
    def __init__(self, name: str) -> None:
        self.name = name.encode('ascii')

        self.__handlers = {}  # type: Dict[bytes, CommandHandler]

    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def add_handler(
            self,
            command: str,
            handler: Callable,
            request_cls: Type[protobuf.Message],
            response_cls: Type[protobuf.Message],
    ) -> None:
        command_b = command.encode('ascii')
        assert command_b not in self.__handlers
        self.__handlers[command_b] = CommandHandler(
            command_b, handler, request_cls, response_cls)

    def remove_handler(self, command: str) -> None:
        command_b = command.encode('ascii')
        if command_b in self.__handlers:
            del self.__handlers[command_b]

    def get_handler(self, command: bytes) -> CommandHandler:
        return self.__handlers[command]


class ServerEndpoint(BaseServerEndpoint):
    REQ = TypeVar('REQ', bound=protobuf.Message)
    RESP = TypeVar('RESP', bound=protobuf.Message)
    def add_handler(
            self,
            command: str,
            handler: Callable[[REQ, RESP], Union[Coroutine, None]],
            request_cls: Type[REQ],
            response_cls: Type[RESP],
    ) -> None:
        super().add_handler(command, handler, request_cls, response_cls)


SESSION = TypeVar('SESSION', bound=Session)
class ServerEndpointWithSessions(Generic[SESSION], BaseServerEndpoint):
    def __init__(
            self,
            name: str,
            session_cls: Type[SESSION],
            session_started: Callable[[SESSION], Awaitable[None]] = None,
            session_ended: Callable[[SESSION], Awaitable[None]] = None) -> None:
        super().__init__(name)

        self.__session_cls = session_cls
        self.__session_started = session_started
        self.__session_ended = session_ended

        self.__sessions = {}  # type: Dict[int, SESSION]

    REQ = TypeVar('REQ', bound=protobuf.Message)
    RESP = TypeVar('RESP', bound=protobuf.Message)
    def add_handler(
            self,
            command: str,
            handler: Callable[[SESSION, REQ, RESP], Union[Coroutine, None]],
            request_cls: Type[REQ],
            response_cls: Type[RESP],
    ) -> None:
        super().add_handler(command, handler, request_cls, response_cls)

    @property
    def sessions(self) -> List[SESSION]:
        return list(self.__sessions.values())

    async def create_session(
            self,
            session_id: int,
            start_session_request: ipc_pb2.StartSessionRequest,
            event_loop: asyncio.AbstractEventLoop,
    ) -> SESSION:
        logger.info("Creating new session %016x...", session_id)
        session = self.__session_cls(session_id, start_session_request, event_loop)
        await session.setup()
        self.__sessions[session_id] = session
        if self.__session_started is not None:
            await self.__session_started(session)
        return session

    async def delete_session(self, session_id: int) -> None:
        session = self.__sessions.pop(session_id)
        await session.cleanup()
        if self.__session_ended is not None:
            await self.__session_ended(session)
        logger.info("Session %016x deleted.", session_id)

    def get_session(self, session_id: int) -> Session:
        return self.__sessions[session_id]


class Server(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, name: str, socket_dir: str) -> None:
        self.event_loop = event_loop
        self.name = name
        self.id = uuid.uuid4().hex

        self.logger = logger.getChild(name)

        self.__socket_path = os.path.join(socket_dir, '%s.%s.sock' % (self.name, self.id))
        self.address = 'ipc://%s@%s' % ('main', self.__socket_path)

        self.__server = None  # type: asyncio.AbstractServer
        self.__active_connections = {}  # type: Dict[int, ServerProtocol]
        self.__endpoints = {}  # type: Dict[bytes, BaseServerEndpoint]

        self.stat_bytes_sent = None  # type: stats.Counter
        self.stat_bytes_received = None  # type: stats.Counter

    @property
    def closed(self) -> bool:
        return self.__server is None

    def endpoint_address(self, name: str) -> str:
        return 'ipc://%s@%s' % (name, self.__socket_path)

    async def add_endpoint(self, endpoint: BaseServerEndpoint) -> str:
        assert endpoint.name not in self.__endpoints
        await endpoint.setup()
        self.__endpoints[endpoint.name] = endpoint
        return self.endpoint_address(endpoint.name.decode('ascii'))

    async def remove_endpoint(self, name: str) -> None:
        endpoint = self.__endpoints.pop(name.encode('ascii'))
        await endpoint.cleanup()

    def get_endpoint(self, name: bytes) -> BaseServerEndpoint:
        return self.__endpoints[name]

    def __getitem__(self, name: str) -> BaseServerEndpoint:
        return self.__endpoints[name.encode('ascii')]

    async def setup(self) -> None:
        self.stat_bytes_sent = stats.registry.register(
            stats.Counter,
            stats.StatName(
                name='ipc_server_bytes_sent',
                server_name=self.name,
                server_id=self.id))
        self.stat_bytes_received = stats.registry.register(
            stats.Counter,
            stats.StatName(
                name='ipc_server_bytes_received',
                server_name=self.name,
                server_id=self.id))

        self.logger.info("%s: Creating server on socket %s", self.id, self.__socket_path)
        self.__server = await self.event_loop.create_unix_server(
            functools.partial(ServerProtocol, self),
            path=self.__socket_path)
        self.logger.info("%s: Listening on socket %s", self.id, self.__socket_path)

    async def cleanup(self) -> None:
        for endpoint in self.__endpoints.values():
            await endpoint.cleanup()
        self.__endpoints.clear()

        if self.__server is not None:
            server = self.__server
            self.__server = None

            server.close()
            await server.wait_closed()

            if os.path.isfile(self.address):
                os.unlink(self.address)

            self.logger.info("%s: Server closed", self.id)

        for conn in self.__active_connections.values():
            conn.drain()

        while self.__active_connections:
            conn = next(iter(self.__active_connections.values()))
            await conn.wait_closed()

        if self.stat_bytes_sent is not None:
            self.stat_bytes_sent.unregister()
            self.stat_bytes_sent = None

        if self.stat_bytes_received is not None:
            self.stat_bytes_received.unregister()
            self.stat_bytes_received = None

    async def __aenter__(self) -> 'Server':
        await self.setup()
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.cleanup()
        return False

    def add_connection(self, connection: ServerProtocol) -> None:
        self.__active_connections[connection.id] = connection

    def remove_connection(self, connection: ServerProtocol) -> None:
        del self.__active_connections[connection.id]


class ClientProtocol(FrameProtocol):
    def __init__(self, stub: 'Stub', event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(logger)
        self.__stub = stub
        self.__closed = asyncio.Event(loop=event_loop)

    async def wait_closed(self) -> None:
        await self.__closed.wait()

    def connection_lost(self, exc: Exception) -> None:
        super().connection_lost(exc)
        self.logger.info("%s: Connection lost.", self.__stub.id)
        self.__closed.set()
        self.__stub.connection_lost()

    def handle_message(self, frames: List[bytes]) -> None:
        self.__stub.handle_response(frames, self.transport)


class Stub(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, server_address: str) -> None:
        self.id = uuid.uuid4().hex
        self.__event_loop = event_loop
        self.__server_address = server_address

        p = urllib.parse.urlparse(server_address)
        assert p.scheme == 'ipc', server_address
        assert p.username, server_address
        assert not p.password, server_address
        assert not p.hostname, server_address
        assert not p.port, server_address
        assert p.path, server_address
        assert not p.params, server_address
        assert not p.query, server_address
        assert not p.fragment, server_address
        self.__endpoint_name = p.username.encode('ascii')
        self.__socket_path = p.path

        self.__transport = None  # type: asyncio.WriteTransport
        self.__protocol = None  # type: ClientProtocol
        self.__pending_requests = None  # type: Dict[int, asyncio.Future[bytes]]
        self.__session_id = None  # type: int
        self.__connected = False
        self.__lock = asyncio.Lock(loop=event_loop)

    @property
    def server_address(self) -> str:
        return self.__server_address

    @property
    def connected(self) -> bool:
        return self.__connected

    @property
    def session_id(self) -> int:
        return self.__session_id

    async def connect(
            self, start_session_request: Optional[ipc_pb2.StartSessionRequest] = None) -> None:
        async with self.__lock:
            assert not self.__connected

            self.__pending_requests = {}

            try:
                transport, protocol = (
                    await self.__event_loop.create_unix_connection(
                        functools.partial(ClientProtocol, self, self.__event_loop),
                        self.__socket_path))
            except IOError as exc:
                raise ConnectionFailedError(
                    "Failed to connect to %s: %s" % (self.__server_address, exc))

            self.__transport = cast(asyncio.WriteTransport, transport)
            self.__protocol = cast(ClientProtocol, protocol)
            logger.info("%s: Connected to server at %s", self.id, self.__server_address)

            start_session_frames = [self.__endpoint_name]
            if start_session_request is not None:
                start_session_frames.append(start_session_request.SerializeToString())
            serialized_response = await self.__call_internal(b'S', start_session_frames)
            if serialized_response:
                self.__session_id = struct.unpack('=Q', serialized_response)[0]
                logger.info("%s: Session ID = %016x", self.id, self.session_id)

            self.__connected = True

    async def close(self) -> None:
        async with self.__lock:
            if not self.__connected:
                return

            logger.info("%s: Closing stub...", self.id)
            assert self.__transport is not None
            self.__transport.close()
            await self.__protocol.wait_closed()
            logger.info("%s: Connection closed.", self.id)

            self.__transport = None
            self.__protocol = None
            self.__session_id = None

            logger.info("%s: Stub closed.", self.id)
            self.__connected = False

    async def __aenter__(self) -> 'Stub':
        await self.connect()
        return self

    async def __aexit__(self, *argv: Any) -> bool:
        await self.close()
        return False

    def connection_lost(self) -> None:
        for response_future in self.__pending_requests.values():
            response_future.set_exception(ConnectionClosed())

    def handle_response(self, frames: List[bytes], transport: asyncio.WriteTransport) -> None:
        request_id, request_type = request_header.unpack(frames[0])
        response_future = self.__pending_requests[request_id]

        if request_type in (b'C', b'S'):
            if frames[1] == b'OK':
                response_future.set_result(frames[2])

            elif frames[1] == b'EXC':
                response_future.set_exception(
                    RemoteException(self.__server_address, frames[2].decode('utf-8')))

            elif frames[1] == b'CLOSED':
                response_future.set_exception(ConnectionClosed())

            else:
                raise ValueError(frames[1])

        elif request_type == b'P':
            response_future.set_result(b'PONG')

        else:
            raise ValueError(request_type)

    async def __call_internal(self, request_type: bytes, frames: List[bytes]) -> bytes:
        if self.__transport.is_closing():
            raise ConnectionClosed()

        request_id = random.getrandbits(63)
        response_future = asyncio.Future(loop=self.__event_loop)  # type: asyncio.Future[bytes]
        self.__pending_requests[request_id] = response_future
        try:
            frames.insert(0, request_header.pack(request_id, request_type))
            last_idx = len(frames) - 1
            for idx, frame in enumerate(frames):
                self.__transport.write(frame_header.pack(len(frame), idx != last_idx))
                self.__transport.write(frame)

            response = await response_future

        finally:
            del self.__pending_requests[request_id]

        return response

    async def call(
            self, cmd: str, request: protobuf.Message = None, response: protobuf.Message = None
    ) -> None:
        if request is not None:
            payload = request.SerializeToString()
        else:
            payload = b''

        logger.debug("%s: sending %s to %s...", self.id, cmd, self.__server_address)
        start_time = time.time()
        serialized_response = await self.__call_internal(
            b'C', [cmd.encode('ascii'), payload])
        logger.debug(
            "%s: %s to %s finished in %.2fmsec",
            self.id, cmd, self.__server_address, 1000 * (time.time() - start_time))

        if response is not None:
            response.ParseFromString(serialized_response)

    async def ping(self) -> None:
        response = await self.__call_internal(b'P', [])
        assert response == b'PONG', response
