#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
import functools
import io
import logging
from typing import List, Dict  # pylint: disable=unused-import
import uuid

from . import ipc
from . import process_manager

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception):
    pass


class SessionBase(object):
    def __init__(self, *, event_loop: asyncio.AbstractEventLoop):
        self.event_loop = event_loop
        self.id = uuid.uuid4().hex
        self.__closed = False

    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    @property
    def closed(self) -> bool:
        # TODO: should trigger CallbackSessionMixin.session_ended()
        return self.__closed

    def close(self) -> None:
        logger.info("Session %s closed.", self.id)
        self.__closed = True


class CallbackSessionMixin(SessionBase):
    async_connect = True

    def __init__(self, *, callback_address, **kwargs):
        super().__init__(**kwargs)

        self.__callback_address = callback_address
        self.__connect_task = None
        self.__callback_stub = None

    @property
    def callback_alive(self):
        return (
            not self.closed
            and self.__callback_stub is not None
            and self.__callback_stub.connected)

    async def setup(self):
        await super().setup()

        self.__callback_stub = ipc.Stub(self.event_loop, self.__callback_address)
        if self.async_connect:
            self.__connect_task = self.event_loop.create_task(self.__callback_stub.connect())
            self.__connect_task.add_done_callback(self.__callback_connected)
        else:
            self.__connect_task = await self.__callback_stub.connect()

    def __callback_connected(self, task):
        if task.cancelled():
            return

        assert task.done()
        exc = task.exception()
        if exc is not None:
            logger.error("Failed to connect to callback client: %s", exc)
            self.close()
            return

        assert self.__callback_stub.connected
        self.callback_connected()

    async def cleanup(self):
        if self.__connect_task is not None:
            self.__connect_task.cancel()
            self.__connect_task = None

        if self.__callback_stub is not None:
            await self.__callback_stub.close()
            self.__callback_stub = None

    def callback_connected(self):
        pass

    async def callback(self, cmd, *args, **kwargs):
        assert self.callback_alive
        await self.__callback_stub.call(cmd, *args, **kwargs)

    def async_callback(self, cmd, *args, **kwargs):
        assert self.callback_alive

        callback_task = self.event_loop.create_task(
            self.__callback_stub.call(cmd, *args, **kwargs))
        callback_task.add_done_callback(
            functools.partial(self.__callback_done, cmd))

    def __callback_done(self, cmd, task):
        if task.cancelled():
            logger.info("Session %s: %s was cancelled.", self.id, cmd)
            return

        exc = task.exception()
        if isinstance(exc, ipc.ConnectionClosed):
            logger.warning("Session %s: callback connection closed.", self.id)
            self.close()

        elif exc is not None:
            buf = io.StringIO()
            task.print_stack(file=buf)
            logger.error(
                "Session %s: %s failed with exception: %s\n%s",
                self.id, cmd, exc, buf.getvalue())
            self.close()


class SessionHandlerMixin(process_manager.ProcessBase):
    session_cls = None  # type: SessionBase

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__sessions = {}  # type: Dict[str, SessionBase]

    @property
    def sessions(self) -> List[SessionBase]:
        return list(self.__sessions.values())

    async def setup(self) -> None:
        await super().setup()

        self.server.add_command_handler('START_SESSION', self.__handle_start_session)
        self.server.add_command_handler('END_SESSION', self.__handle_end_session)

    async def cleanup(self) -> None:
        if self.server is not None:
            self.server.remove_command_handler('START_SESSION')
            self.server.remove_command_handler('END_SESSION')

        for session in self.__sessions.values():
            logger.info("Cleaning up session %s...", session.id)
            await session.cleanup()
        self.__sessions.clear()

        await super().cleanup()

    def get_session(self, session_id: str) -> SessionBase:
        try:
            return self.__sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    async def session_started(self, session: SessionBase) -> None:
        pass

    async def session_ended(self, session: SessionBase) -> None:
        pass

    async def __handle_start_session(self, *args, **kwargs) -> str:
        session = self.session_cls(  # pylint: disable=not-callable
            *args, event_loop=self.event_loop, **kwargs)
        try:
            assert session.id not in self.__sessions
            await session.setup()

            self.__sessions[session.id] = session
            await self.session_started(session)
            return session.id

        except:  # pylint: disable=broad-except
            await session.cleanup()
            raise

    async def __handle_end_session(self, session_id: str) -> None:
        self.get_session(session_id)
        session = self.__sessions.pop(session_id)
        await session.cleanup()
        await self.session_ended(session)
