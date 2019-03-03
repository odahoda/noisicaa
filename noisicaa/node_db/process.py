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

import logging
from typing import Any

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from .private import db
from . import node_db_pb2

logger = logging.getLogger(__name__)


class Session(ipc.CallbackSessionMixin, ipc.Session):
    async_connect = False

    async def publish_mutation(self, mutation: node_db_pb2.Mutation) -> None:
        await self.callback('NODEDB_MUTATION', mutation)

    def async_publish_mutation(self, mutation: node_db_pb2.Mutation) -> None:
        self.async_callback('NODEDB_MUTATION', mutation)


class NodeDBProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__db = db.NodeDB()
        self.__main_endpoint = None  # type: ipc.ServerEndpointWithSessions[Session]

    async def setup(self) -> None:
        await super().setup()
        self.__db.setup()

        self.__main_endpoint = ipc.ServerEndpointWithSessions(
            'main', Session,
            session_started=self.__session_started)
        self.__main_endpoint.add_handler(
            'START_SCAN', self.__handle_start_scan,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(self.__main_endpoint)

    async def cleanup(self) -> None:
        self.__db.cleanup()
        await super().cleanup()

    def publish_mutation(self, mutation: node_db_pb2.Mutation) -> None:
        for session in self.__main_endpoint.sessions:
            session.async_publish_mutation(mutation)

    async def __session_started(self, session: Session) -> None:
        # Send initial mutations to build up the current pipeline
        # state.
        for mutation in self.__db.initial_mutations():
            await session.publish_mutation(mutation)

    async def __handle_start_scan(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        self.__db.start_scan()


class NodeDBSubprocess(core.SubprocessMixin, NodeDBProcess):
    pass
