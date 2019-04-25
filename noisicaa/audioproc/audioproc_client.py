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
import random
import traceback
from typing import Any, Optional, Iterable, Set, Tuple, Dict

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import session_data_pb2
from noisicaa.core import ipc
from noisicaa import node_db
from noisicaa import lv2
from .public import engine_notification_pb2
from .public import player_state_pb2
from .public import processor_message_pb2
from .public import host_parameters_pb2
from .public import backend_settings_pb2
from .public import project_properties_pb2
from . import audioproc_pb2

logger = logging.getLogger(__name__)


class AbstractAudioProcClient(object):
    def __init__(self) -> None:
        self.engine_notifications = None  # type: core.Callback[engine_notification_pb2.EngineNotification]
        self.engine_state_changed = None  # type: core.Callback[engine_notification_pb2.EngineStateChange]
        self.player_state_changed = None  # type: core.CallbackMap[str, player_state_pb2.PlayerState]
        self.node_state_changed = None  # type: core.CallbackMap[str, engine_notification_pb2.NodeStateChange]
        self.node_messages = None  # type: core.CallbackMap[str, Dict[str, Any]]
        self.perf_stats = None  # type: core.Callback[core.PerfStats]

    @property
    def address(self) -> str:
        raise NotImplementedError

    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    async def connect(self, address: str, flags: Optional[Set[str]] = None) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
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

    async def pipeline_mutation(self, realm: str, mutation: audioproc_pb2.Mutation) -> None:
        raise NotImplementedError

    async def create_plugin_ui(self, realm: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        raise NotImplementedError

    async def delete_plugin_ui(self, realm: str, node_id: str) -> None:
        raise NotImplementedError

    async def send_node_messages(
            self, realm: str, messages: processor_message_pb2.ProcessorMessageList) -> None:
        raise NotImplementedError

    async def set_host_parameters(self, *, block_size: int = None, sample_rate: int = None) -> None:
        raise NotImplementedError

    async def set_backend(
            self, name: str, settings: backend_settings_pb2.BackendSettings = None) -> None:
        raise NotImplementedError

    async def set_session_values(
            self, realm: str, values: Iterable[session_data_pb2.SessionValue]) -> None:
        raise NotImplementedError

    async def update_player_state(self, state: player_state_pb2.PlayerState) -> None:
        raise NotImplementedError

    async def play_file(self, path: str) -> None:
        raise NotImplementedError

    async def update_project_properties(
            self, realm: str, properties: project_properties_pb2.ProjectProperties) -> None:
        raise NotImplementedError

    async def profile_audio_thread(self, duration: int) -> bytes:
        raise NotImplementedError

    async def dump(self) -> None:
        raise NotImplementedError


class AudioProcClient(AbstractAudioProcClient):
    def __init__(
            self,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            urid_mapper: lv2.URIDMapper,
    ) -> None:
        super().__init__()

        self.event_loop = event_loop
        self.server = server
        self.urid_mapper = urid_mapper

        self._stub = None  # type: ipc.Stub

        self.engine_notifications = core.Callback[engine_notification_pb2.EngineNotification]()
        self.engine_state_changed = core.Callback[engine_notification_pb2.EngineStateChange]()
        self.player_state_changed = core.CallbackMap[str, player_state_pb2.PlayerState]()
        self.node_state_changed = core.CallbackMap[str, engine_notification_pb2.NodeStateChange]()
        self.node_messages = core.CallbackMap[str, Dict[str, Any]]()
        self.perf_stats = core.Callback[core.PerfStats]()

        self.__cb_endpoint_name = 'audioproc-%016x' % random.getrandbits(63)
        self.__cb_endpoint_address = None  # type: str

    @property
    def address(self) -> str:
        return self._stub.server_address

    async def setup(self) -> None:
        await super().setup()

        cb_endpoint = ipc.ServerEndpoint(self.__cb_endpoint_name)
        cb_endpoint.add_handler(
            'ENGINE_NOTIFICATION', self.__handle_engine_notification,
            engine_notification_pb2.EngineNotification, empty_message_pb2.EmptyMessage)

        self.__cb_endpoint_address = await self.server.add_endpoint(cb_endpoint)


    async def cleanup(self) -> None:
        await self.disconnect()

        if self.__cb_endpoint_address is not None:
            await self.server.remove_endpoint(self.__cb_endpoint_name)
            self.__cb_endpoint_address = None

        await super().cleanup()

    async def connect(self, address: str, flags: Optional[Set[str]] = None) -> None:
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect(core.StartSessionRequest(
            callback_address=self.__cb_endpoint_address,
            flags=flags))

    async def disconnect(self) -> None:
        if self._stub is not None:
            await self._stub.close()
            self._stub = None

    async def __handle_engine_notification(
            self,
            request: engine_notification_pb2.EngineNotification,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        try:
            self.engine_notifications.call(request)

            if request.HasField('player_state'):
                player_state = request.player_state
                self.player_state_changed.call(player_state.realm, player_state)

            for node_state_change in request.node_state_changes:
                self.node_state_changed.call(node_state_change.node_id, node_state_change)

            for node_message_pb in request.node_messages:
                msg_atom = node_message_pb.atom
                node_message = lv2.wrap_atom(self.urid_mapper, msg_atom).as_object
                self.node_messages.call(node_message_pb.node_id, node_message)

            for engine_state_change in request.engine_state_changes:
                self.engine_state_changed.call(engine_state_change)

            if request.HasField('perf_stats'):
                perf_stats = core.PerfStats()
                perf_stats.deserialize(request.perf_stats)
                self.perf_stats.call(perf_stats)

        except:  # pylint: disable=bare-except
            logger.error(
                "Exception while processing engine notification:\n%s\n==========\n%s",
                request, traceback.format_exc())

    async def create_realm(
            self, *, name: str, parent: Optional[str] = None, enable_player: bool = False,
            callback_address: Optional[str] = None) -> None:
        await self._stub.call(
            'CREATE_REALM',
            audioproc_pb2.CreateRealmRequest(
                name=name,
                parent=parent,
                enable_player=enable_player,
                callback_address=callback_address))

    async def delete_realm(self, name: str) -> None:
        await self._stub.call(
            'DELETE_REALM',
            audioproc_pb2.DeleteRealmRequest(
                name=name))

    async def add_node(
            self, realm: str, *, description: node_db.NodeDescription, **args: Any) -> None:
        await self.pipeline_mutation(
            realm,
            audioproc_pb2.Mutation(
                add_node=audioproc_pb2.AddNode(description=description, **args)))

    async def remove_node(self, realm: str, node_id: str) -> None:
        await self.pipeline_mutation(
            realm,
            audioproc_pb2.Mutation(
                remove_node=audioproc_pb2.RemoveNode(id=node_id)))

    async def connect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        await self.pipeline_mutation(
            realm,
            audioproc_pb2.Mutation(
                connect_ports=audioproc_pb2.ConnectPorts(
                    src_node_id=node1_id,
                    src_port=port1_name,
                    dest_node_id=node2_id,
                    dest_port=port2_name)))

    async def disconnect_ports(
            self, realm: str, node1_id: str, port1_name: str, node2_id: str, port2_name: str
    ) -> None:
        await self.pipeline_mutation(
            realm,
            audioproc_pb2.Mutation(
                disconnect_ports=audioproc_pb2.DisconnectPorts(
                    src_node_id=node1_id,
                    src_port=port1_name,
                    dest_node_id=node2_id,
                    dest_port=port2_name)))

    async def set_control_value(self, realm: str, name: str, value: float, generation: int) -> None:
        await self.pipeline_mutation(
            realm,
            audioproc_pb2.Mutation(
                set_control_value=audioproc_pb2.SetControlValue(
                    name=name,
                    value=value,
                    generation=generation)))

    async def pipeline_mutation(self, realm: str, mutation: audioproc_pb2.Mutation) -> None:
        await self._stub.call(
            'PIPELINE_MUTATION',
            audioproc_pb2.PipelineMutationRequest(
                realm=realm,
                mutation=mutation))

    async def create_plugin_ui(self, realm: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        request = audioproc_pb2.CreatePluginUIRequest(
            realm=realm,
            node_id=node_id)
        response = audioproc_pb2.CreatePluginUIResponse()
        await self._stub.call('CREATE_PLUGIN_UI', request, response)
        return (response.wid, (response.width, response.height))

    async def delete_plugin_ui(self, realm: str, node_id: str) -> None:
        await self._stub.call(
            'DELETE_PLUGIN_UI',
            audioproc_pb2.DeletePluginUIRequest(
                realm=realm,
                node_id=node_id))

    async def send_node_messages(
            self, realm: str, messages: processor_message_pb2.ProcessorMessageList) -> None:
        await self._stub.call(
            'SEND_NODE_MESSAGES',
            audioproc_pb2.SendNodeMessagesRequest(
                realm=realm,
                messages=messages.messages))

    async def set_host_parameters(self, *, block_size: int = None, sample_rate: int = None) -> None:
        await self._stub.call(
            'SET_HOST_PARAMETERS',
            host_parameters_pb2.HostParameters(
                block_size=block_size,
                sample_rate=sample_rate))

    async def set_backend(
            self, name: str, settings: backend_settings_pb2.BackendSettings = None) -> None:
        await self._stub.call(
            'SET_BACKEND',
            audioproc_pb2.SetBackendRequest(
                name=name,
                settings=settings))

    async def set_session_values(
            self, realm: str, values: Iterable[session_data_pb2.SessionValue]) -> None:
        await self._stub.call(
            'SET_SESSION_VALUES',
            audioproc_pb2.SetSessionValuesRequest(
                realm=realm,
                session_values=values))

    async def update_player_state(self, state: player_state_pb2.PlayerState) -> None:
        await self._stub.call(
            'UPDATE_PLAYER_STATE',
            state)

    async def play_file(self, path: str) -> None:
        await self._stub.call(
            'PLAY_FILE',
            audioproc_pb2.PlayFileRequest(
                path=path))

    async def profile_audio_thread(self, duration: int) -> bytes:
        request = audioproc_pb2.ProfileAudioThreadRequest(
            duration=duration)
        response = audioproc_pb2.ProfileAudioThreadResponse()
        await self._stub.call('PROFILE_AUDIO_THREAD', request, response)
        return response.svg

    async def update_project_properties(
            self, realm: str, properties: project_properties_pb2.ProjectProperties) -> None:
        await self._stub.call(
            'UPDATE_PROJECT_PROPERTIES',
            audioproc_pb2.UpdateProjectPropertiesRequest(
                realm=realm,
                properties=properties))

    async def dump(self) -> None:
        await self._stub.call('DUMP')
