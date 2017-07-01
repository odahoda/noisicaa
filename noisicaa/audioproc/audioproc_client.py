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
        self.listeners = core.CallbackRegistry()

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PIPELINE_MUTATION', self.handle_pipeline_mutation)
        self.server.add_command_handler(
            'PIPELINE_STATUS', self.handle_pipeline_status,
            log_level=-1)

    async def cleanup(self):
        await self.disconnect()
        self.server.remove_command_handler('PIPELINE_MUTATION')
        self.server.remove_command_handler('PIPELINE_STATUS')
        await super().cleanup()

    async def connect(self, address, flags=None):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call(
            'START_SESSION', self.server.address, flags)

    async def disconnect(self, shutdown=False):
        if self._session_id is not None:
            try:
                await self._stub.call('END_SESSION', self._session_id)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
            self._session_id = None

        if self._stub is not None:
            if shutdown:
                await self.shutdown()

            await self._stub.close()
            self._stub = None

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def add_node(self, node_type, **args):
        return await self._stub.call('ADD_NODE', self._session_id, node_type, args)

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

    async def set_backend(self, name, **parameters):
        return await self._stub.call(
            'SET_BACKEND', self._session_id, name, parameters)

    async def set_backend_parameters(self, **parameters):
        return await self._stub.call(
            'SET_BACKEND_PARAMETERS', self._session_id, parameters)

    async def play_file(self, path):
        return await self._stub.call(
            'PLAY_FILE', self._session_id, path)

    async def add_event(self, entity_id, event):
        return await self._stub.call(
            'ADD_EVENT', self._session_id, entity_id, event)

    async def set_port_property(self, node_id, port_name, **kwargs):
        return await self._stub.call(
            'SET_PORT_PROP', self._session_id, node_id, port_name, kwargs)

    async def set_node_parameter(self, node_id, **kwargs):
        return await self._stub.call(
            'SET_NODE_PARAM', self._session_id, node_id, kwargs)

    async def dump(self):
        return await self._stub.call('DUMP', self._session_id)

    def handle_pipeline_mutation(self, mutation):
        logger.info("Mutation received: %s" % mutation)

    def handle_pipeline_status(self, status):
        logger.info("Status update received: %s" % status)
        self.listeners.call('pipeline_status', status)
