#!/usr/bin/python3

import asyncio
import functools
import logging
import time
import uuid

from noisicaa import constants
from noisicaa import core
from noisicaa.core import ipc

from .private import db

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub, flags):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.flags = flags or set()
        self.id = uuid.uuid4().hex
        self.pending_mutations = []

    def cleanup(self):
        pass

    def publish_mutations(self, mutations):
        if not self.callback_stub.connected:
            self.pending_mutations.extend(mutations)
            return

        callback_task = self.event_loop.create_task(
            self.callback_stub.call('INSTRUMENTDB_MUTATIONS', mutations))
        callback_task.add_done_callback(self.publish_mutations_done)

    def publish_mutations_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error(
                "INSTRUMENTDB_MUTATIONS failed with exception: %s", exc)

    def callback_stub_connected(self):
        assert self.callback_stub.connected
        self.publish_mutations(self.pending_mutations)
        self.pending_mutations.clear()


class InstrumentDBProcessMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = {}
        self.db = None
        self.search_paths = [
            '/usr/share/sounds/sf2/',
            '/storage/home/share/samples/',
        ]

    async def setup(self):
        await super().setup()

        self._shutting_down = asyncio.Event()
        self._shutdown_complete = asyncio.Event()

        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.server.add_command_handler(
            'START_SCAN', self.handle_start_scan)

        self.db = db.InstrumentDB(self.event_loop, constants.CACHE_DIR)
        self.db.setup()
        self.db.add_mutations_listener(self.publish_mutations)
        if time.time() - self.db.last_scan_time > 3600:
            self.db.start_scan(self.search_paths, True)

    async def cleanup(self):
        if self.db is not None:
            self.db.cleanup()
            self.db = None

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

    def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        session.cleanup()
        del self.sessions[session_id]

    async def handle_shutdown(self):
        logger.info("Shutdown received.")
        self._shutting_down.set()
        logger.info("Waiting for shutdown to complete...")
        await self._shutdown_complete.wait()
        logger.info("Shutdown complete.")

    async def handle_start_scan(self, session_id):
        self.get_session(session_id)
        return self.db.start_scan(self.search_paths, True)


class InstrumentDBProcess(InstrumentDBProcessMixin, core.ProcessImpl):
    pass
