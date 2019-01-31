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
import logging
import os
import os.path
import pickle
import pprint
import time
import traceback
from typing import cast, Any, Optional, Dict, Tuple, Callable, Type
import uuid

from google.protobuf import message as protobuf

from . import stats

logger = logging.getLogger(__name__)


class RemoteException(Exception):
    def __init__(self, server_address: str, tb: str) -> None:
        super().__init__("From server %s:\n%s" % (server_address, tb))

class Error(Exception):
    pass

class ConnectionFailedError(Error):
    pass

class InvalidResponseError(Error):
    pass

class ConnectionClosed(Error):
    pass


class ConnState(enum.Enum):
    READ_MESSAGE = 1
    READ_PAYLOAD = 2


class ServerProtocol(asyncio.Protocol):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, server: 'Server') -> None:
        self.event_loop = event_loop
        self.server = server
        self.id = server.new_connection_id()
        self.transport = None  # type: asyncio.WriteTransport
        self.state = ConnState.READ_MESSAGE
        self.command = None  # type: str
        self.payload_length = None  # type: int
        self.inbuf = bytearray()
        self.logger = server.logger.getChild("conn-%d" % self.id)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.logger.info("Accepted new connection.")
        self.transport = cast(asyncio.WriteTransport, transport)

    def connection_lost(self, exc: Exception) -> None:
        self.logger.info("Connection closed.")

    def data_received(self, data: bytes) -> None:
        if self.server.closed:
            self.logger.warning("Received data in closed server.")
            return

        self.inbuf.extend(data)
        self.server.stat_bytes_received.incr(len(data))

        while self.inbuf:
            if self.state == ConnState.READ_MESSAGE:
                try:
                    eol = self.inbuf.index(b'\n')
                except ValueError:
                    break

                header = bytes(self.inbuf[:eol])
                self.inbuf = self.inbuf[eol+1:]
                if header == b'PING':
                    self.logger.debug("PING received")
                    response = b'ACK 4\nPONG'
                    self.transport.write(response)
                    self.server.stat_bytes_sent.incr(len(response))

                elif header.startswith(b'CALL '):
                    command, length = header[5:].split(b' ')
                    self.command = command.decode('ascii')
                    self.payload_length = int(length)
                    #self.logger.debug(
                    #    "CALL %s received (%d bytes payload)", self.command, self.payload_length)
                    if self.payload_length > 0:
                        self.state = ConnState.READ_PAYLOAD
                    else:
                        task = self.event_loop.create_task(
                            self.server.handle_command(self.command, None))
                        task.add_done_callback(self.command_complete)
                else:
                    self.logger.error("Received unknown message '%s'", header)
            elif self.state == ConnState.READ_PAYLOAD:
                if len(self.inbuf) < self.payload_length:
                    break
                payload = bytes(self.inbuf[:self.payload_length])
                del self.inbuf[:self.payload_length]
                task = self.event_loop.create_task(
                    self.server.handle_command(self.command, payload))
                task.add_done_callback(self.command_complete)
                self.state = ConnState.READ_MESSAGE
                self.command = None
                self.payload_length = None

    def command_complete(self, task: asyncio.Task) -> None:
        if task.exception() is not None:
            raise task.exception()

        response = task.result() or b''
        header = b'ACK %d\n' % len(response)
        self.transport.write(header)
        # TODO: uncomment when Server.cleanup waits for outstanding commands
        #self.server.stat_bytes_sent.incr(len(header))
        if response:
            self.transport.write(response)
            #self.server.stat_bytes_sent.incr(len(response))


class Server(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, name: str, socket_dir: str) -> None:
        self.event_loop = event_loop
        self.name = name
        self.id = uuid.uuid4().hex

        self.logger = logger.getChild(name)

        self.address = os.path.join(socket_dir, '%s.%s.sock' % (self.name, self.id))

        self.__next_connection_id = 0
        self.__server = None  # type: asyncio.AbstractServer

        self.__command_handlers = {}  # type: Dict[str, Tuple[Callable, Type[protobuf.Message], Type[protobuf.Message]]
        self.__command_log_levels = {}  # type: Dict[str, int]

        self.stat_bytes_sent = None  # type: stats.Counter
        self.stat_bytes_received = None  # type: stats.Counter

    @property
    def closed(self) -> bool:
        return self.__server is None

    def add_command_handler(
            self,
            cmd: str,
            handler: Callable[..., Any],
            request_cls: Type[protobuf.Message] = None,
            response_cls: Type[protobuf.Message] = None,
            *,
            log_level: Optional[int] = -1
    ) -> None:
        assert cmd not in self.__command_handlers
        self.__command_handlers[cmd] = (handler, request_cls, response_cls)
        if log_level is not None:
            self.__command_log_levels[cmd] = log_level

    def remove_command_handler(self, cmd: str) -> None:
        if cmd in self.__command_handlers:
            del self.__command_handlers[cmd]

    def new_connection_id(self) -> int:
        self.__next_connection_id += 1
        return self.__next_connection_id

    def serialize(self, payload: Any) -> bytes:
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize(self, serialized_payload: bytes) -> Any:
        return pickle.loads(serialized_payload)

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

        self.logger.info("%s: Creating server on socket %s", self.id, self.address)
        self.__server = await self.event_loop.create_unix_server(
            functools.partial(ServerProtocol, self.event_loop, self),
            path=self.address)
        self.logger.info("%s: Listening on socket %s", self.id, self.address)

    async def cleanup(self) -> None:
        if self.__server is not None:
            self.__server.close()
            await self.__server.wait_closed()

            if os.path.isfile(self.address):
                os.unlink(self.address)

            self.__server = None
            self.logger.info("%s: Server closed", self.id)

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

    # def send_close(self):
    #     sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    #     sock.connect(self.address)
    #     sock.sendall(b'CLOSE\n')
    #     sock.close()

    # def wait_for_pending_connections(self):
    #     while len(self.__connections) > 0:
    #         time.sleep(0.01)

    async def handle_command(self, command: str, payload: bytes) -> bytes:
        try:
            handler, request_cls, response_cls = self.__command_handlers[command]

            if request_cls is not None:
                request = request_cls()
                request.ParseFromString(payload)
                response = response_cls()

                if asyncio.iscoroutinefunction(handler):
                    await handler(request, response)
                else:
                    handler(request, response)

                return b'OK:' + response.SerializeToString()

            else:
                args, kwargs = self.deserialize(payload)

                log_level = self.__command_log_levels.get(command, logging.INFO)
                if log_level >= 0:
                    logger.log(
                        log_level,
                        "%s(%s%s)",
                        command,
                        ', '.join(str(a) for a in args),
                        ''.join(', %s=%r' % (k, v)
                                for k, v in sorted(kwargs.items())))

                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*args, **kwargs)
                else:
                    result = handler(*args, **kwargs)

                if result is not None:
                    return b'OK:' + self.serialize(result)
                else:
                    return b'OK'

        except Exception:  # pylint: disable=broad-except
            return b'EXC:' + str(traceback.format_exc()).encode('utf-8')


class ClientProtocol(asyncio.Protocol):
    def __init__(self, stub: 'Stub', event_loop: asyncio.AbstractEventLoop) -> None:
        self.stub = stub
        self.closed_event = asyncio.Event(loop=event_loop)
        self.state = 0
        self.buf = bytearray()
        self.length = None  # type: int
        self.response = None  # type: bytes
        self.response_queue = asyncio.Queue(loop=event_loop)  # type: asyncio.Queue

    def connection_lost(self, exc: Exception) -> None:
        self.closed_event.set()
        logger.info("%s: Connection lost.", self.stub.id)
        self.response_queue.put_nowait(self.stub.CLOSE_SENTINEL)

    def data_received(self, data: bytes) -> None:
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


class ResponseContainer(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.response = None  # type: bytes
        self.__event = asyncio.Event(loop=event_loop)

    def set(self, response: bytes) -> None:
        self.response = response
        self.__event.set()

    async def wait(self) -> bytes:
        await self.__event.wait()
        return self.response


class Stub(object):
    CLOSE_SENTINEL = object()

    def __init__(self, event_loop: asyncio.AbstractEventLoop, server_address: str) -> None:
        self.id = uuid.uuid4().hex
        self.__event_loop = event_loop
        self.__server_address = server_address
        self.__transport = None  # type: asyncio.WriteTransport
        self.__protocol = None  # type: ClientProtocol
        self.__command_queue = None  # type: asyncio.Queue
        self.__command_loop_cancelled = None  # type: asyncio.Event
        self.__command_loop_task = None  # type: asyncio.Task
        self.__connected = False
        self.__lock = asyncio.Lock(loop=event_loop)

    @property
    def server_address(self) -> str:
        return self.__server_address

    @property
    def connected(self) -> bool:
        return self.__connected

    def serialize(self, payload: Any) -> bytes:
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize(self, serialized_payload: bytes) -> Any:
        return pickle.loads(serialized_payload)

    async def connect(self) -> None:
        async with self.__lock:
            assert not self.__connected

            try:
                transport, protocol = (
                    await self.__event_loop.create_unix_connection(
                        functools.partial(ClientProtocol, self, self.__event_loop),
                        self.__server_address))
            except IOError as exc:
                raise ConnectionFailedError(
                    "Failed to connect to %s: %s" % (self.__server_address, exc))

            self.__transport = cast(asyncio.WriteTransport, transport)
            self.__protocol = cast(ClientProtocol, protocol)
            logger.info("%s: Connected to server at %s", self.id, self.__server_address)

            self.__command_queue = asyncio.Queue(loop=self.__event_loop)
            self.__command_loop_cancelled = asyncio.Event(loop=self.__event_loop)
            self.__command_loop_task = self.__event_loop.create_task(self.command_loop())

            self.__connected = True

    async def close(self) -> None:
        async with self.__lock:
            if not self.__connected:
                return

            logger.info("%s: Closing stub...", self.id)
            assert self.__transport is not None
            self.__transport.close()
            await self.__protocol.closed_event.wait()
            logger.info("%s: Connection closed.", self.id)

            if self.__command_loop_task is not None:
                self.__command_loop_cancelled.set()
                await asyncio.wait_for(self.__command_loop_task, None, loop=self.__event_loop)
                logger.info("%s: Command queue cleaned up.", self.id)
                self.__command_loop_task = None

            self.__command_queue = None
            self.__transport = None
            self.__protocol = None

            logger.info("%s: Stub closed.", self.id)
            self.__connected = True

    async def __aenter__(self) -> 'Stub':
        await self.connect()
        return self

    async def __aexit__(self, *argv: Any) -> bool:
        await self.close()
        return False

    async def command_loop(self) -> None:
        cancelled_task = asyncio.ensure_future(
            self.__command_loop_cancelled.wait(), loop=self.__event_loop)
        while not self.__command_loop_cancelled.is_set():
            get_task = asyncio.ensure_future(self.__command_queue.get(), loop=self.__event_loop)
            done, _ = await asyncio.wait(
                [get_task, cancelled_task],
                return_when=asyncio.FIRST_COMPLETED,
                loop=self.__event_loop)
            if get_task not in done:
                get_task.cancel()
                continue

            cmd, payload, response_container = get_task.result()

            if self.__transport.is_closing():
                response_container.set(self.CLOSE_SENTINEL)
                continue

            logger.debug(
                "%s: sending %s to %s...", self.id, cmd.decode('utf-8'), self.__server_address)
            start_time = time.time()
            self.__transport.write(b'CALL %s %d\n' % (cmd, len(payload)))
            if payload:
                self.__transport.write(payload)

            response = await self.__protocol.response_queue.get()
            logger.debug(
                "%s: %s to %s finished in %.2fmsec",
                self.id, cmd.decode('utf-8'), self.__server_address,
                1000 * (time.time() - start_time))
            response_container.set(response)

        cancelled_task.cancel()

    async def call(self, cmd: str, *args: Any, **kwargs: Any) -> Any:
        try:
            payload = self.serialize([args, kwargs])
        except TypeError as exc:
            raise TypeError(
                "%s:\nargs=%s\nkwargs=%s" % (
                    exc, pprint.pformat(args), pprint.pformat(kwargs))
            ) from None

        response_container = ResponseContainer(self.__event_loop)
        self.__command_queue.put_nowait((cmd.encode('ascii'), payload, response_container))
        response = await response_container.wait()

        if response is self.CLOSE_SENTINEL:
            raise ConnectionClosed(self.id)
        elif response == b'OK':
            return None
        elif response.startswith(b'OK:'):
            return self.deserialize(response[3:])
        elif response.startswith(b'EXC:'):
            raise RemoteException(self.__server_address, response[4:].decode('utf-8'))
        else:
            raise InvalidResponseError(response)

    async def proto_call(
            self, cmd: str, request: protobuf.Message, response: protobuf.Message
    ) -> None:
        payload = request.SerializeToString()

        response_container = ResponseContainer(self.__event_loop)
        self.__command_queue.put_nowait((cmd.encode('ascii'), payload, response_container))
        serialized_response = await response_container.wait()

        if serialized_response is self.CLOSE_SENTINEL:
            raise ConnectionClosed(self.id)
        elif serialized_response.startswith(b'OK:'):
            response.ParseFromString(serialized_response[3:])
        elif serialized_response.startswith(b'EXC:'):
            raise RemoteException(self.__server_address, serialized_response[4:].decode('utf-8'))
        else:
            raise InvalidResponseError(serialized_response)

    def call_sync(self, cmd: str, payload: bytes = b'') -> Any:
        return self.__event_loop.run_until_complete(self.call(cmd, payload))

    async def ping(self) -> None:
        self.__transport.write(b'PING\n')
        response = await self.__protocol.response_queue.get()
        assert response == b'PONG', response
