#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.core import ipc
from . import mutations

logger = logging.getLogger(__name__)


class InstrumentDBClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None
        self._instruments = {}
        self.listeners = core.CallbackRegistry()

    @property
    def instruments(self):
        return sorted(
            self._instruments.values(), key=lambda i: i.display_name.lower())

    def get_instrument_description(self, uri):
        return self._instrument[uri]

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'INSTRUMENTDB_MUTATIONS', self.handle_mutation)

    async def connect(self, address, flags=None):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call(
            'START_SESSION', self.server.address, flags)

    async def disconnect(self, shutdown=False):
        if self._session_id is not None:
            await self._stub.call('END_SESSION', self._session_id)
            self._session_id = None

        if self._stub is not None:
            if shutdown:
                await self.shutdown()

            await self._stub.close()
            self._stub = None

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def start_scan(self):
        return await self._stub.call('START_SCAN', self._session_id)

    def handle_mutation(self, mutation_list):
        for mutation in mutation_list:
            logger.info("Mutation received: %s" % mutation)
            if isinstance(mutation, mutations.AddInstrumentDescription):
                self._instruments[mutation.description.uri] = mutation.description
            else:
                raise ValueError(mutation)

            self.listeners.call('mutation', mutation)
