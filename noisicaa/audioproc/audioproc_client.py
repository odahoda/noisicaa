#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class AudioProcClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stubs = {}

    async def setup(self):
        pass

    async def get_stub(self, address):
        stub = AudioProcStub(self.event_loop, address)
        await stub.connect()
        session_id = await stub.start_session(self.server.address)
        self._stubs[session_id] = stub
        return stub


class AudioProcStub(ipc.Stub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_id = None

    async def shutdown(self):
        await self.call('SHUTDOWN')

    async def start_session(self, callback_server):
        self._session_id = await self.call('START_SESSION', callback_server)
        return self._session_id

    async def end_session(self):
        assert self._session_id is not None
        await self.call('END_SESSION', self._session_id)
