#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
import logging
from typing import Any, Optional, Set, Tuple, Dict

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import node_db
from .public import engine_notification_pb2
from .public import player_state_pb2
from .public import processor_message_pb2
from . import mutations

logger = logging.getLogger(__name__)


class AudioProcClientBase(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, server: ipc.Server) -> None:
        self.event_loop = event_loop
        self.server = server

        self.engine_notifications = None  # type: core.Callback[engine_notification_pb2.EngineNotification]
        self.engine_state_changed = None  # type: core.Callback[engine_notification_pb2.EngineStateChange]
        self.player_state_changed = None  # type: core.CallbackMap[str, player_state_pb2.PlayerState]
        self.node_state_changed = None  # type: core.CallbackMap[str, engine_notification_pb2.NodeStateChange]
        self.node_messages = None  # type: core.CallbackMap[str, bytes]
        self.perf_stats = None  # type: core.Callback[core.PerfStats]

    @property
    def address(self) -> str:
        raise NotImplementedError

    async def setup(self) -> None:
        raise NotImplementedError

    async def cleanup(self) -> None:
        raise NotImplementedError

    async def connect(self, address: str, flags: Optional[Set[str]] = None) -> None:
        raise NotImplementedError

    async def disconnect(self, shutdown: bool = False) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        raise NotImplementedError

    async def ping(self) -> None:
        raise NotImplementedError

    async def create_realm(
            self, *, name: str, parent: Optional[str] = None, enable_player: bool = False,
            callback_address: Optional[str] = None) -> None:
        raise NotImplementedError

    async def delete_realm(self, name: str) -> None:
        raise NotImplementedError

    async def add_node(
            self, realm: str, *, description: node_db.NodeDescription, **args: Any) -> None:
        raise NotImplementedError

    async def remove_node(self, realm: str, node_id: str) -> None:
        raise NotImplementedError

    async def connect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        raise NotImplementedError

    async def disconnect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        raise NotImplementedError

    async def set_control_value(self, realm: str, name: str, value: float, generation: int) -> None:
        raise NotImplementedError

    async def pipeline_mutation(self, realm: str, mutation: mutations.Mutation) -> None:
        raise NotImplementedError

    async def create_plugin_ui(self, realm: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        raise NotImplementedError

    async def delete_plugin_ui(self, realm: str, node_id: str) -> None:
        raise NotImplementedError

    async def send_node_messages(
            self, realm: str, messages: processor_message_pb2.ProcessorMessageList) -> None:
        raise NotImplementedError

    async def set_host_parameters(self, **parameters: Any) -> None:
        raise NotImplementedError

    async def set_backend(self, name: str, **parameters: Any) -> None:
        raise NotImplementedError

    async def set_backend_parameters(self, **parameters: Any) -> None:
        raise NotImplementedError

    async def set_session_values(self, realm: str, values: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def update_player_state(self, state: player_state_pb2.PlayerState) -> None:
        raise NotImplementedError

    async def play_file(self, path: str) -> None:
        raise NotImplementedError

    async def dump(self) -> None:
        raise NotImplementedError

    async def update_project_properties(self, realm: str, **kwargs: Any) -> None:
        raise NotImplementedError


class AudioProcClientMixin(AudioProcClientBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stub = None  # type: ipc.Stub
        self._session_id = None  # type: str

        self.engine_notifications = core.Callback[engine_notification_pb2.EngineNotification]()
        self.engine_state_changed = core.Callback[engine_notification_pb2.EngineStateChange]()
        self.player_state_changed = core.CallbackMap[str, player_state_pb2.PlayerState]()
        self.node_state_changed = core.CallbackMap[str, engine_notification_pb2.NodeStateChange]()
        self.node_messages = core.CallbackMap[str, bytes]()
        self.perf_stats = core.Callback[core.PerfStats]()

    @property
    def address(self) -> str:
        return self._stub.server_address

    async def setup(self) -> None:
        await super().setup()
        self.server.add_command_handler(
            'ENGINE_NOTIFICATION', self.__handle_engine_notification, log_level=logging.DEBUG)

    async def cleanup(self) -> None:
        await self.disconnect()
        self.server.remove_command_handler('ENGINE_NOTIFICATION')
        await super().cleanup()

    async def connect(self, address: str, flags: Optional[Set[str]] = None) -> None:
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call('START_SESSION', self.server.address, flags)
        logger.info("Started session %s", self._session_id)

    async def disconnect(self, shutdown: bool = False) -> None:
        if self._session_id is not None:
            try:
                await self._stub.call('END_SESSION', self._session_id)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
            self._session_id = None

        if self._stub is not None:
            if shutdown:
                try:
                    await self.shutdown()
                except ipc.ConnectionClosed:
                    pass

            await self._stub.close()
            self._stub = None

    async def __handle_engine_notification(
            self, msg: engine_notification_pb2.EngineNotification) -> None:
        self.engine_notifications.call(msg)

        if msg.HasField('player_state'):
            player_state = msg.player_state
            self.player_state_changed.call(player_state.realm, player_state)

        for node_state_change in msg.node_state_changes:
            self.node_state_changed.call(node_state_change.node_id, node_state_change)

        for node_message in msg.node_messages:
            self.node_messages.call(node_message.node_id, node_message.atom)

        for engine_state_change in msg.engine_state_changes:
            self.engine_state_changed.call(engine_state_change)

        if msg.HasField('perf_stats'):
            perf_stats = core.PerfStats()
            perf_stats.deserialize(msg.perf_stats)
            self.perf_stats.call(perf_stats)

    async def shutdown(self) -> None:
        await self._stub.call('SHUTDOWN')

    async def ping(self) -> None:
        await self._stub.ping()

    async def create_realm(
            self, *, name: str, parent: Optional[str] = None, enable_player: bool = False,
            callback_address: Optional[str] = None) -> None:
        await self._stub.call(
            'CREATE_REALM', self._session_id, name, parent, enable_player, callback_address)

    async def delete_realm(self, name: str) -> None:
        await self._stub.call('DELETE_REALM', self._session_id, name)

    async def add_node(
            self, realm: str, *, description: node_db.NodeDescription, **args: Any) -> None:
        await self.pipeline_mutation(realm, mutations.AddNode(description=description, **args))

    async def remove_node(self, realm: str, node_id: str) -> None:
        await self.pipeline_mutation(realm, mutations.RemoveNode(node_id))

    async def connect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        await self.pipeline_mutation(
            realm, mutations.ConnectPorts(node1_id, port1_name, node2_id, port2_name))

    async def disconnect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        await self.pipeline_mutation(
            realm, mutations.DisconnectPorts(node1_id, port1_name, node2_id, port2_name))

    async def set_control_value(self, realm: str, name: str, value: float, generation: int) -> None:
        await self.pipeline_mutation(realm, mutations.SetControlValue(name, value, generation))

    async def pipeline_mutation(self, realm: str, mutation: mutations.Mutation) -> None:
        await self._stub.call('PIPELINE_MUTATION', self._session_id, realm, mutation)

    async def create_plugin_ui(self, realm: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self._stub.call('CREATE_PLUGIN_UI', self._session_id, realm, node_id)

    async def delete_plugin_ui(self, realm: str, node_id: str) -> None:
        await self._stub.call('DELETE_PLUGIN_UI', self._session_id, realm, node_id)

    async def send_node_messages(
            self, realm: str, messages: processor_message_pb2.ProcessorMessageList) -> None:
        await self._stub.call('SEND_NODE_MESSAGES', self._session_id, realm, messages)

    async def set_host_parameters(self, **parameters: Any) -> None:
        await self._stub.call('SET_HOST_PARAMETERS', self._session_id, parameters)

    async def set_backend(self, name: str, **parameters: Any) -> None:
        await self._stub.call('SET_BACKEND', self._session_id, name, parameters)

    async def set_backend_parameters(self, **parameters: Any) -> None:
        await self._stub.call('SET_BACKEND_PARAMETERS', self._session_id, parameters)

    async def set_session_values(self, realm: str, values: Dict[str, Any]) -> None:
        await self._stub.call('SET_SESSION_VALUES', self._session_id, realm, values)

    async def update_player_state(self, state: player_state_pb2.PlayerState) -> None:
        await self._stub.call('UPDATE_PLAYER_STATE', self._session_id, state)

    async def play_file(self, path: str) -> None:
        await self._stub.call('PLAY_FILE', self._session_id, path)

    async def dump(self) -> None:
        await self._stub.call('DUMP', self._session_id)

    async def profile_audio_thread(self, duration: int) -> bytes:
        return await self._stub.call('PROFILE_AUDIO_THREAD', self._session_id, duration)

    async def update_project_properties(self, realm: str, **kwargs: Any) -> None:
        return await self._stub.call('UPDATE_PROJECT_PROPERTIES', self._session_id, realm, kwargs)
