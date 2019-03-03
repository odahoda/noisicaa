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
from typing import Dict, Set, Iterable

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from . import instrument_db_pb2
from . import instrument_description_pb2

logger = logging.getLogger(__name__)


class InstrumentDBClient(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, server: ipc.Server) -> None:
        self.event_loop = event_loop
        self.server = server

        self.mutation_handlers = core.Callback[instrument_db_pb2.Mutation]()

        self.__cb_endpoint_name = 'instrument_db_cb'  # type: str
        self.__cb_endpoint_address = None  # type: str
        self.__stub = None  # type: ipc.Stub
        self.__instruments = {}  # type: Dict[str, instrument_description_pb2.InstrumentDescription]

    @property
    def instruments(self) -> Iterable[instrument_description_pb2.InstrumentDescription]:
        return sorted(
            self.__instruments.values(), key=lambda i: i.display_name.lower())

    def get_instrument_description(
            self, uri: str) -> instrument_description_pb2.InstrumentDescription:
        return self.__instruments[uri]

    async def setup(self) -> None:
        cb_endpoint = ipc.ServerEndpoint(self.__cb_endpoint_name)
        cb_endpoint.add_handler(
            'INSTRUMENTDB_MUTATIONS', self.__handle_mutation,
            instrument_db_pb2.Mutations, empty_message_pb2.EmptyMessage)
        self.__cb_endpoint_address = await self.server.add_endpoint(cb_endpoint)

    async def cleanup(self) -> None:
        await self.disconnect()
        if self.__cb_endpoint_address is not None:
            await self.server.remove_endpoint(self.__cb_endpoint_name)
            self.__cb_endpoint_address = None

    async def connect(self, address: str, flags: Set[str] = None) -> None:
        assert self.__stub is None
        self.__stub = ipc.Stub(self.event_loop, address)
        await self.__stub.connect(core.StartSessionRequest(
            callback_address=self.__cb_endpoint_address,
            flags=flags))

    async def disconnect(self) -> None:
        if self.__stub is not None:
            await self.__stub.close()
            self.__stub = None

    async def start_scan(self) -> None:
        await self.__stub.call('START_SCAN')

    def __handle_mutation(
            self,
            request: instrument_db_pb2.Mutations,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        for mutation in request.mutations:
            logger.info("Mutation received: %s", mutation)
            if mutation.WhichOneof('type') == 'add_instrument':
                self.__instruments[mutation.add_instrument.uri] = mutation.add_instrument
            else:
                raise ValueError(mutation)

            self.mutation_handlers.call(mutation)
