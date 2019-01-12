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
from typing import cast, Any, Set

from noisicaa import core
from .private import db
from . import process_base
from . import mutations

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    async_connect = False

    def __init__(self, client_address: str, flags: Set[str], **kwargs: Any) -> None:
        super().__init__(callback_address=client_address, **kwargs)
        self.__flags = flags or set()

    async def publish_mutation(self, mutation: mutations.Mutation) -> None:
        await self.callback('NODEDB_MUTATION', mutation)

    def async_publish_mutation(self, mutation: mutations.Mutation) -> None:
        self.async_callback('NODEDB_MUTATION', mutation)


class NodeDBProcess(process_base.NodeDBProcessBase):
    session_cls = Session

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = db.NodeDB()

    async def setup(self) -> None:
        await super().setup()
        self.db.setup()

    async def cleanup(self) -> None:
        self.db.cleanup()
        await super().cleanup()

    def publish_mutation(self, mutation: mutations.Mutation) -> None:
        for session in self.sessions:
            session = cast(Session, session)
            session.async_publish_mutation(mutation)

    async def session_started(self, session: core.SessionBase) -> None:
        session = cast(Session, session)
        # Send initial mutations to build up the current pipeline
        # state.
        for mutation in self.db.initial_mutations():
            await session.publish_mutation(mutation)

    async def handle_start_scan(self, session_id: str) -> None:
        self.get_session(session_id)
        self.db.start_scan()


class NodeDBSubprocess(core.SubprocessMixin, NodeDBProcess):
    pass
