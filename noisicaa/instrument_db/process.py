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
import logging
import time
from typing import Any

from noisicaa import constants
from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc

from .private import db
from . import instrument_db_pb2

logger = logging.getLogger(__name__)


class Session(ipc.CallbackSessionMixin, ipc.Session):
    def __init__(
            self,
            session_id: int,
            start_session_request: core.StartSessionRequest,
            event_loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__(session_id, start_session_request, event_loop)
        self.__flags = set(start_session_request.flags)
        self.__pending_mutations = instrument_db_pb2.Mutations()

    def callback_connected(self) -> None:
        logger.info(
            "Client callback connection established, sending %d pending mutations.",
            len(self.__pending_mutations.mutations))
        self.publish_mutations(self.__pending_mutations)
        self.__pending_mutations = instrument_db_pb2.Mutations()

    def publish_mutations(self, mutations: instrument_db_pb2.Mutations) -> None:
        if not mutations.mutations:
            return

        if not self.callback_alive:
            self.__pending_mutations.mutations.extend(mutations.mutations)
            return

        self.async_callback('INSTRUMENTDB_MUTATIONS', mutations)


class InstrumentDBProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__main_endpoint = None  # type: ipc.ServerEndpointWithSessions[Session]
        self.__db = None  # type: db.InstrumentDB
        self.__search_paths = [
            '/usr/share/sounds/sf2/',
            '/data/instruments/',
        ]

    async def setup(self) -> None:
        await super().setup()

        self.__db = db.InstrumentDB(self.event_loop, constants.CACHE_DIR)
        self.__db.setup()
        self.__db.add_mutations_listener(self.publish_mutations)
        if time.time() - self.__db.last_scan_time > 3600:
            self.__db.start_scan(self.__search_paths, True)

        self.__main_endpoint = ipc.ServerEndpointWithSessions(
            'main', Session,
            session_started=self.__session_started)
        self.__main_endpoint.add_handler(
            'START_SCAN', self.__handle_start_scan,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(self.__main_endpoint)

    async def cleanup(self) -> None:
        if self.__db is not None:
            self.__db.cleanup()
            self.__db = None

        await super().cleanup()

    def publish_mutations(self, mutations: instrument_db_pb2.Mutations) -> None:
        for session in self.__main_endpoint.sessions:
            session.publish_mutations(mutations)

    async def __session_started(self, session: Session) -> None:
        # Send initial mutations to build up the current pipeline state.
        session.publish_mutations(self.__db.initial_mutations())

    async def __handle_start_scan(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        self.__db.start_scan(self.__search_paths, True)


class InstrumentDBSubprocess(core.SubprocessMixin, InstrumentDBProcess):
    pass
