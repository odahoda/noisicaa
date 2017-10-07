#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import logging
import uuid

from noisicaa import core
from noisicaa.core import ipc

from .private import db
from . import process_base

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub, flags):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.flags = flags or set()
        self.id = uuid.uuid4().hex

    async def cleanup(self):
        if self.callback_stub is not None:
            await self.callback_stub.close()
            self.callback_stub = None

    async def publish_mutation(self, mutation):
        assert self.callback_stub.connected
        await self.callback_stub.call('NODEDB_MUTATION', mutation)


class NodeDBProcess(process_base.NodeDBProcessBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = {}
        self.db = db.NodeDB()

    async def setup(self):
        await super().setup()

        self._shutting_down = asyncio.Event()
        self._shutdown_complete = asyncio.Event()

        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()
        await super().cleanup()

    async def run(self):
        await self._shutting_down.wait()
        logger.info("Shutting down...")
        self._shutdown_complete.set()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def publish_mutation(self, mutation):
        for session in self.sessions.values():
            session.publish_mutation(mutation)

    async def handle_start_session(self, client_address, flags):
        client_stub = ipc.Stub(self.event_loop, client_address)
        await client_stub.connect()
        session = Session(self.event_loop, client_stub, flags)
        self.sessions[session.id] = session

        # Send initial mutations to build up the current pipeline
        # state.
        for mutation in self.db.initial_mutations():
            await session.publish_mutation(mutation)

        return session.id

    async def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        await session.cleanup()
        del self.sessions[session_id]

    async def handle_shutdown(self):
        logger.info("Shutdown received.")
        self._shutting_down.set()
        logger.info("Waiting for shutdown to complete...")
        await self._shutdown_complete.wait()
        logger.info("Shutdown complete.")

    async def handle_start_scan(self, session_id):
        self.get_session(session_id)
        return self.db.start_scan()


class NodeDBSubprocess(core.SubprocessMixin, NodeDBProcess):
    pass
