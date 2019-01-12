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
from typing import cast, Any, Dict

from noisicaa import core
from . import urid_mapper

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    async_connect = False

    def __init__(self, client_address: str, **kwargs: Any) -> None:
        super().__init__(callback_address=client_address, **kwargs)

    async def publish_new_uri(self, uris: Dict[str, int]) -> None:
        assert self.callback_alive
        await self.callback('NEW_URIS', uris)


class URIDMapperProcess(core.SessionHandlerMixin, core.ProcessBase):
    session_cls = Session

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__mapper = urid_mapper.PyDynamicURIDMapper()

    async def setup(self) -> None:
        await super().setup()

        self.server.add_command_handler('MAP', self.handle_map)
        self.server.add_command_handler('SHUTDOWN', self.shutdown)

    async def session_started(self, session: core.SessionBase) -> None:
        initial_uris = dict(self.__mapper.list())
        if initial_uris:
            await cast(Session, session).publish_new_uri(initial_uris)

    async def handle_map(self, uri: str) -> int:
        publish = not self.__mapper.known(uri)
        urid = self.__mapper.map(uri)
        if publish:
            tasks = []
            for session in self.sessions:
                tasks.append(cast(Session, session).publish_new_uri({uri: urid}))

            await asyncio.wait(tasks, loop=self.event_loop)
        return urid


class URIDMapperSubprocess(core.SubprocessMixin, URIDMapperProcess):
    pass
