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

# TODO: mypy-unclean

import logging

from noisicaa import core
from noisicaa.core import ipc

from . import mutations

logger = logging.getLogger(__name__)


class AudioProcClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None
        self.listeners = core.CallbackRegistry()

    @property
    def address(self):
        return self._stub.server_address

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PIPELINE_MUTATION', self.handle_pipeline_mutation)
        self.server.add_command_handler(
            'PLAYER_STATE', self.handle_player_state, log_level=-1)
        self.server.add_command_handler(
            'PIPELINE_STATUS', self.handle_pipeline_status, log_level=-1)

    async def cleanup(self):
        await self.disconnect()
        self.server.remove_command_handler('PIPELINE_MUTATION')
        self.server.remove_command_handler('PLAYER_STATE')
        self.server.remove_command_handler('PIPELINE_STATUS')
        await super().cleanup()

    async def connect(self, address, flags=None):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call('START_SESSION', self.server.address, flags)
        logger.info("Started session %s", self._session_id)

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

    async def ping(self):
        await self._stub.ping()

    async def create_realm(self, *, name, parent=None, enable_player=False):
        await self._stub.call('CREATE_REALM', self._session_id, name, parent, enable_player)

    async def delete_realm(self, name):
        await self._stub.call('DELETE_REALM', self._session_id, name)

    async def add_node(self, realm, *, description, **args):
        return await self.pipeline_mutation(
            realm, mutations.AddNode(description=description, **args))

    async def remove_node(self, realm, node_id):
        return await self.pipeline_mutation(
            realm, mutations.RemoveNode(node_id))

    async def connect_ports(self, realm, node1_id, port1_name, node2_id, port2_name):
        return await self.pipeline_mutation(
            realm, mutations.ConnectPorts(node1_id, port1_name, node2_id, port2_name))

    async def disconnect_ports(self, realm, node1_id, port1_name, node2_id, port2_name):
        return await self.pipeline_mutation(
            realm, mutations.DisconnectPorts(node1_id, port1_name, node2_id, port2_name))

    async def set_port_property(self, realm, node_id, port_name, **kwargs):
        return await self.pipeline_mutation(
            realm, mutations.SetPortProperty(node_id, port_name, **kwargs))

    async def set_control_value(self, realm, name, value):
        return await self.pipeline_mutation(
            realm, mutations.SetControlValue(name, value))

    async def pipeline_mutation(self, realm, mutation):
        return await self._stub.call(
            'PIPELINE_MUTATION', self._session_id, realm, mutation)

    async def create_plugin_ui(self, realm, node_id):
        return await self._stub.call('CREATE_PLUGIN_UI', self._session_id, realm, node_id)

    async def delete_plugin_ui(self, realm, node_id):
        return await self._stub.call('DELETE_PLUGIN_UI', self._session_id, realm, node_id)

    async def send_node_messages(self, realm, messages):
        return await self._stub.call(
            'SEND_NODE_MESSAGES', self._session_id, realm, messages)

    async def set_host_parameters(self, **parameters):
        return await self._stub.call(
            'SET_HOST_PARAMETERS', self._session_id, parameters)

    async def set_backend(self, name, **parameters):
        return await self._stub.call(
            'SET_BACKEND', self._session_id, name, parameters)

    async def set_backend_parameters(self, **parameters):
        return await self._stub.call(
            'SET_BACKEND_PARAMETERS', self._session_id, parameters)

    async def update_player_state(self, realm, state):
        return await self._stub.call(
            'UPDATE_PLAYER_STATE', self._session_id, realm, state)

    async def send_message(self, msg):
        return await self._stub.call('SEND_MESSAGE', self._session_id, msg.to_bytes())

    async def play_file(self, path):
        return await self._stub.call(
            'PLAY_FILE', self._session_id, path)

    async def dump(self):
        return await self._stub.call('DUMP', self._session_id)

    async def update_project_properties(self, realm, **kwargs):
        return await self._stub.call(
            'UPDATE_PROJECT_PROPERTIES', self._session_id, realm, kwargs)

    def handle_pipeline_mutation(self, mutation):
        logger.info("Mutation received: %s", mutation)

    def handle_pipeline_status(self, status):
        self.listeners.call('pipeline_status', status)

    def handle_player_state(self, realm, state):
        self.listeners.call('player_state', realm, state)
