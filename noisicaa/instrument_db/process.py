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

import functools
import logging
import time
import uuid

from noisicaa import constants
from noisicaa import core
from noisicaa.core import ipc

from .private import db
from . import process_base

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception):
    pass


class Session(object):
    def __init__(self, event_loop, callback_stub, flags):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.flags = flags or set()
        self.id = uuid.uuid4().hex
        self.pending_mutations = []

    async def cleanup(self):
        if self.callback_stub is not None:
            await self.callback_stub.close()
            self.callback_stub = None

    def publish_mutations(self, mutations):
        if not mutations:
            return

        if not self.callback_stub.connected:
            self.pending_mutations.extend(mutations)
            return

        callback_task = self.event_loop.create_task(
            self.callback_stub.call('INSTRUMENTDB_MUTATIONS', list(mutations)))
        callback_task.add_done_callback(self.publish_mutations_done)

    def publish_mutations_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error(
                "INSTRUMENTDB_MUTATIONS failed with exception: %s", exc)

    def callback_stub_connected(self):
        logger.info(
            "Client callback connection established, sending %d pending mutations.",
            len(self.pending_mutations))
        assert self.callback_stub.connected
        self.publish_mutations(self.pending_mutations)
        self.pending_mutations.clear()


class InstrumentDBProcess(process_base.InstrumentDBProcessBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = {}
        self.db = None
        self.search_paths = [
            '/usr/share/sounds/sf2/',
            '/data/instruments/',
        ]

    async def setup(self):
        await super().setup()

        self.db = db.InstrumentDB(self.event_loop, constants.CACHE_DIR)
        self.db.setup()
        self.db.add_mutations_listener(self.publish_mutations)
        if time.time() - self.db.last_scan_time > 3600:
            self.db.start_scan(self.search_paths, True)

    async def cleanup(self):
        for session in self.sessions.values():
            await session.cleanup()
        self.sessions.clear()

        if self.db is not None:
            self.db.cleanup()
            self.db = None

        await super().cleanup()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def publish_mutations(self, mutations):
        for session in self.sessions.values():
            session.publish_mutations(mutations)

    def handle_start_session(self, client_address, flags):
        client_stub = ipc.Stub(self.event_loop, client_address)
        connect_task = self.event_loop.create_task(client_stub.connect())
        session = Session(self.event_loop, client_stub, flags)
        connect_task.add_done_callback(
            functools.partial(self._client_connected, session))
        self.sessions[session.id] = session

        # Send initial mutations to build up the current pipeline
        # state.
        session.publish_mutations(list(self.db.initial_mutations()))

        return session.id

    def _client_connected(self, session, connect_task):
        assert connect_task.done()
        exc = connect_task.exception()
        if exc is not None:
            logger.error("Failed to connect to callback client: %s", exc)
            return

        session.callback_stub_connected()

    async def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        await session.cleanup()
        del self.sessions[session_id]

    async def handle_start_scan(self, session_id):
        self.get_session(session_id)
        return self.db.start_scan(self.search_paths, True)


class InstrumentDBSubprocess(core.SubprocessMixin, InstrumentDBProcess):
    pass
