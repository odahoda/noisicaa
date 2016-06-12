#!/usr/bin/python3

import logging

from noisicaa import core

from . import project_stub

logger = logging.getLogger(__name__)


class ProjectClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stubs = {}

    async def setup(self):
        self.server.add_command_handler(
            'LISTENER_CALLBACK', self.handle_listener_callback)

    def register_stub(self, session_id, stub):
        self._stubs[session_id] = stub

    def handle_listener_callback(self, session_id, listener_id, args):
        try:
            stub = self._stubs[session_id]
        except KeyError:
            logger.error(
                "Got LISTENER_CALLBACK for unknown session %s", session_id)
        else:
            stub.listener_callback(listener_id, args)

    async def get_stub(self, address):
        stub = project_stub.ProjectStub(self.event_loop, address)
        await stub.connect()
        session_id = await stub.start_session(self.server.address)
        self._stubs[session_id] = stub
        return stub


class ProjectClient(core.ProcessImpl, ProjectClientMixin):
    pass
