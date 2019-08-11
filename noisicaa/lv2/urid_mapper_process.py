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
from typing import Any

from noisicaa import core
from noisicaa.core import ipc
from . import urid_mapper_pb2
from . import urid_mapper

logger = logging.getLogger(__name__)


class Session(ipc.CallbackSessionMixin, ipc.Session):
    async_connect = False

    async def publish_new_uri(self, uris: urid_mapper_pb2.NewURIsRequest) -> None:
        assert self.callback_alive
        await self.callback('NEW_URIS', uris)


class URIDMapperProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__main_endpoint = None  # type: ipc.ServerEndpointWithSessions[Session]
        self.__mapper = urid_mapper.PyDynamicURIDMapper()

    async def setup(self) -> None:
        await super().setup()

        self.__main_endpoint = ipc.ServerEndpointWithSessions(
            'main', Session,
            session_started=self.__session_started)
        self.__main_endpoint.add_handler(
            'MAP', self.__handle_map,
            urid_mapper_pb2.MapRequest, urid_mapper_pb2.MapResponse)
        await self.server.add_endpoint(self.__main_endpoint)

    async def __session_started(self, session: Session) -> None:
        initial_uris = urid_mapper_pb2.NewURIsRequest()
        for uri, urid in self.__mapper.list():
            initial_uris.mappings.add(uri=uri, urid=urid)
        if initial_uris.mappings:
            await session.publish_new_uri(initial_uris)

    async def __handle_map(
            self,
            session: Session,
            request: urid_mapper_pb2.MapRequest,
            response: urid_mapper_pb2.MapResponse
    ) -> None:
        publish = not self.__mapper.known(request.uri)
        urid = self.__mapper.map(request.uri)
        if publish:
            new_uris = urid_mapper_pb2.NewURIsRequest()
            new_uris.mappings.add(uri=request.uri, urid=urid)

            tasks = []
            for session in self.__main_endpoint.sessions:
                tasks.append(session.publish_new_uri(new_uris))
            await asyncio.wait(tasks, loop=self.event_loop)

        response.urid = urid


class URIDMapperSubprocess(core.SubprocessMixin, URIDMapperProcess):
    pass
