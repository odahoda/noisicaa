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

import logging

from noisicaa import core
from .private import db
from . import process_base

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    async_connect = False

    def __init__(self, client_address, flags, **kwargs):
        super().__init__(callback_address=client_address, **kwargs)
        self.flags = flags or set()

    async def publish_mutation(self, mutation):
        await self.callback('NODEDB_MUTATION', mutation)

    def async_publish_mutation(self, mutation):
        self.async_callback('NODEDB_MUTATION', mutation)


class NodeDBProcess(process_base.NodeDBProcessBase):
    session_cls = Session

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = db.NodeDB()

    async def setup(self):
        await super().setup()

        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()
        await super().cleanup()

    def publish_mutation(self, mutation):
        for session in self.sessions:
            session.async_publish_mutation(mutation)

    async def session_started(self, session):
        # Send initial mutations to build up the current pipeline
        # state.
        for mutation in self.db.initial_mutations():
            await session.publish_mutation(mutation)

    async def handle_start_scan(self, session_id):
        self.get_session(session_id)
        return self.db.start_scan()


class NodeDBSubprocess(core.SubprocessMixin, NodeDBProcess):
    pass
