#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class AudioProcClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PIPELINE_MUTATION', self.handle_pipeline_mutation)
        self.server.add_command_handler(
            'PIPELINE_STATUS', self.handle_pipeline_status)

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call(
            'START_SESSION', self.server.address)

    async def disconnect(self):
        if self._session_id is not None:
            await self._stub.call('END_SESSION', self._session_id)
            self._session_id = None

        if self._stub is not None:
            await self._stub.close()
            self._stub = None

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def list_node_types(self):
        return await self._stub.call('LIST_NODE_TYPES', self._session_id)

    async def add_node(self, name, **args):
        return await self._stub.call('ADD_NODE', self._session_id, name, args)

    async def remove_node(self, node_id):
        return await self._stub.call('REMOVE_NODE', self._session_id, node_id)

    async def connect_ports(self, node1_id, port1_name, node2_id, port2_name):
        return await self._stub.call(
            'CONNECT_PORTS', self._session_id,
            node1_id, port1_name, node2_id, port2_name)

    async def disconnect_ports(
        self, node1_id, port1_name, node2_id, port2_name):
        return await self._stub.call(
            'DISCONNECT_PORTS', self._session_id,
            node1_id, port1_name, node2_id, port2_name)

    def handle_pipeline_mutation(self, mutation):
        logger.info("Mutation received: %s" % mutation)

    def handle_pipeline_status(self, status):
        logger.info("Status update received: %s" % status)
