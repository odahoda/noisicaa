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
import logging
from typing import Dict, Iterable, Set, Tuple

from noisicaa import core
from noisicaa.core import ipc
from . import mutations
from . import node_description_pb2

logger = logging.getLogger(__name__)


class NodeDBClient(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, server: ipc.Server) -> None:
        self.event_loop = event_loop
        self.server = server

        self.mutation_handlers = core.Callback[mutations.Mutation]()

        self.__stub = None  # type: ipc.Stub
        self.__session_id = None  # type: str
        self.__nodes = {}  # type: Dict[str, node_description_pb2.NodeDescription]

    def get_node_description(self, uri: str) -> node_description_pb2.NodeDescription:
        return self.__nodes[uri]

    @property
    def nodes(self) -> Iterable[Tuple[str, node_description_pb2.NodeDescription]]:
        return sorted(self.__nodes.items())

    async def setup(self) -> None:
        self.server.add_command_handler('NODEDB_MUTATION', self.__handle_mutation)

    async def cleanup(self) -> None:
        await self.disconnect()

    async def connect(self, address: str, flags: Set[str] = None) -> None:
        assert self.__stub is None
        self.__stub = ipc.Stub(self.event_loop, address)
        await self.__stub.connect()
        self.__session_id = await self.__stub.call(
            'START_SESSION', self.server.address, flags)

    async def disconnect(self, shutdown: bool = False) -> None:
        if self.__session_id is not None:
            try:
                await self.__stub.call('END_SESSION', self.__session_id)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
            self.__session_id = None

        if self.__stub is not None:
            if shutdown:
                await self.shutdown()

            await self.__stub.close()
            self.__stub = None

    async def shutdown(self) -> None:
        await self.__stub.call('SHUTDOWN')

    async def start_scan(self) -> None:
        await self.__stub.call('START_SCAN', self.__session_id)

    def __handle_mutation(self, mutation: mutations.Mutation) -> None:
        logger.info("Mutation received: %s", mutation)
        if isinstance(mutation, mutations.AddNodeDescription):
            assert mutation.uri not in self.__nodes
            self.__nodes[mutation.uri] = mutation.description
        else:
            raise ValueError(mutation)

        self.mutation_handlers.call(mutation)
