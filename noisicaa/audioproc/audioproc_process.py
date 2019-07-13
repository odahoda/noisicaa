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
import functools
import logging
import subprocess
import sys
import time
import uuid
from typing import Any, Optional, Dict, Set

import posix_ipc

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa import node_db
from noisicaa import lv2
from noisicaa import host_system
from noisicaa import editor_main_pb2
from .public import engine_notification_pb2
from .public import host_parameters_pb2
from .public import player_state_pb2
from .engine import profile
from . import engine
from . import audioproc_pb2

logger = logging.getLogger(__name__)


class Session(ipc.CallbackSessionMixin, ipc.Session):
    async_connect = False

    def __init__(
            self,
            session_id: int,
            start_session_request: core.StartSessionRequest,
            event_loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__(session_id, start_session_request, event_loop)

        self.__flags = set(start_session_request.flags)
        self.owned_realms = set()  # type: Set[str]

        self.__shutdown = False
        self.__notification_pusher_task = None  # type: asyncio.Task
        self.__notification_available = None  # type: asyncio.Event
        self.__pending_notification = engine_notification_pb2.EngineNotification()

    async def setup(self) -> None:
        await super().setup()

        self.__shutdown = False
        self.__notification_available = asyncio.Event(loop=self._event_loop)
        self.__notification_pusher_task = self._event_loop.create_task(
            self.__notification_pusher())

    async def cleanup(self) -> None:
        if self.__notification_pusher_task is not None:
            self.__shutdown = True
            self.__notification_available.set()
            await self.__notification_pusher_task
            self.__notification_pusher_task.result()
            self.__notification_pusher_task = None

        await super().cleanup()

    async def __notification_pusher(self) -> None:
        while True:
            await self.__notification_available.wait()
            self.__notification_available.clear()
            next_notification = time.time() + 1.0/50

            if self.__shutdown:
                return

            if not self.callback_alive:
                continue

            notification = self.__pending_notification
            self.__pending_notification = engine_notification_pb2.EngineNotification()
            await self.callback('ENGINE_NOTIFICATION', notification)

            delay = next_notification - time.time()
            if delay > 0:
                await asyncio.sleep(delay, loop=self._event_loop)

    def callback_connected(self) -> None:
        pass

    def publish_engine_notification(self, msg: engine_notification_pb2.EngineNotification) -> None:
        # TODO: filter out message for not owned realms
        self.__pending_notification.MergeFrom(msg)
        self.__notification_available.set()


class AudioProcProcess(core.ProcessBase):
    def __init__(
            self, *,
            shm: Optional[str] = None,
            block_size: Optional[int] = None,
            sample_rate: Optional[int] = None,
            **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.shm_name = shm
        self.shm = None  # type: Optional[posix_ipc.SharedMemory]

        self.__main_endpoint = None  # type: ipc.ServerEndpointWithSessions[Session]
        self.__urid_mapper = None  # type: lv2.ProxyURIDMapper
        self.__block_size = block_size
        self.__sample_rate = sample_rate
        self.__host_system = None  # type: host_system.HostSystem
        self.__engine = None  # type: engine.Engine

    async def setup(self) -> None:
        await super().setup()

        self.__main_endpoint = ipc.ServerEndpointWithSessions('main', Session)
        self.__main_endpoint.add_handler(
            'CREATE_REALM', self.__handle_create_realm,
            audioproc_pb2.CreateRealmRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'DELETE_REALM', self.__handle_delete_realm,
            audioproc_pb2.DeleteRealmRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'SET_HOST_PARAMETERS', self.__handle_set_host_parameters,
            host_parameters_pb2.HostParameters, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'SET_BACKEND', self.__handle_set_backend,
            audioproc_pb2.SetBackendRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'SET_SESSION_VALUES', self.__handle_set_session_values,
            audioproc_pb2.SetSessionValuesRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'PLAY_FILE', self.__handle_play_file,
            audioproc_pb2.PlayFileRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'PIPELINE_MUTATION', self.__handle_pipeline_mutation,
            audioproc_pb2.PipelineMutationRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'SEND_NODE_MESSAGES', self.__handle_send_node_messages,
            audioproc_pb2.SendNodeMessagesRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'UPDATE_PLAYER_STATE', self.__handle_update_player_state,
            player_state_pb2.PlayerState, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'UPDATE_PROJECT_PROPERTIES', self.__handle_update_project_properties,
            audioproc_pb2.UpdateProjectPropertiesRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'CREATE_PLUGIN_UI', self.__handle_create_plugin_ui,
            audioproc_pb2.CreatePluginUIRequest, audioproc_pb2.CreatePluginUIResponse)
        self.__main_endpoint.add_handler(
            'DELETE_PLUGIN_UI', self.__handle_delete_plugin_ui,
            audioproc_pb2.DeletePluginUIRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'PROFILE_AUDIO_THREAD', self.__handle_profile_audio_thread,
            audioproc_pb2.ProfileAudioThreadRequest, audioproc_pb2.ProfileAudioThreadResponse)
        self.__main_endpoint.add_handler(
            'DUMP', self.__handle_dump,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(self.__main_endpoint)

        if self.shm_name is not None:
            self.shm = posix_ipc.SharedMemory(self.shm_name)

        create_urid_mapper_response = editor_main_pb2.CreateProcessResponse()
        await self.manager.call(
            'CREATE_URID_MAPPER_PROCESS', None, create_urid_mapper_response)
        urid_mapper_address = create_urid_mapper_response.address

        self.__urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=self.tmp_dir)
        await self.__urid_mapper.setup(self.event_loop)

        self.__host_system = host_system.HostSystem(self.__urid_mapper)
        if self.__block_size is not None:
            self.__host_system.set_block_size(self.__block_size)
        if self.__sample_rate is not None:
            self.__host_system.set_sample_rate(self.__sample_rate)
        self.__host_system.setup()

        self.__engine = engine.Engine(
            event_loop=self.event_loop,
            manager=self.manager,
            server_address=self.server.address,
            host_system=self.__host_system,
            shm=self.shm)
        self.__engine.notifications.add(
            lambda msg: self.event_loop.call_soon_threadsafe(
                functools.partial(self.__handle_engine_notification, msg)))

        await self.__engine.setup()

    async def cleanup(self) -> None:
        logger.info("Cleaning up AudioProcProcess %s...", self.name)

        if self.shm is not None:
            self.shm.close_fd()
            self.shm = None

        if self.__engine is not None:
            logger.info("Cleaning up engine...")
            await self.__engine.cleanup()
            self.__engine = None

        if self.__host_system is not None:
            logger.info("Cleaning up HostSystem...")
            self.__host_system.cleanup()
            self.__host_system = None

        if self.__urid_mapper is not None:
            logger.info("Cleaning up ProxyURIDMapper...")
            await self.__urid_mapper.cleanup(self.event_loop)
            self.__urid_mapper = None

        await super().cleanup()

    def __handle_engine_notification(self, msg: engine_notification_pb2.EngineNotification) -> None:
        for session in self.__main_endpoint.sessions:
            session.publish_engine_notification(msg)

    async def __handle_create_realm(
            self,
            session: Session,
            request: audioproc_pb2.CreateRealmRequest,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        await self.__engine.create_realm(
            name=request.name,
            parent=request.parent if request.HasField('parent') else None,
            enable_player=request.enable_player,
            callback_address=(
                request.callback_address if request.HasField('callback_address') else None))
        session.owned_realms.add(request.name)

    async def __handle_delete_realm(
            self,
            session: Session,
            request: audioproc_pb2.DeleteRealmRequest,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        assert request.name in session.owned_realms
        await self.__engine.delete_realm(request.name)
        session.owned_realms.remove(request.name)

    async def __handle_pipeline_mutation(
            self,
            session: Session,
            request: audioproc_pb2.PipelineMutationRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        logging.info("Pipeline mutation:\n%s", request)

        realm = self.__engine.get_realm(request.realm)
        graph = realm.graph

        mutation_type = request.mutation.WhichOneof('type')
        if mutation_type == 'add_node':
            add_node = request.mutation.add_node
            logger.info("AddNode():\n%s", add_node.description)
            kwargs = {}  # type: Dict[str, Any]
            if add_node.HasField('name'):
                kwargs['name'] = add_node.name
            if add_node.HasField('initial_state'):
                kwargs['initial_state'] = add_node.initial_state
            if add_node.HasField('child_realm'):
                kwargs['child_realm'] = add_node.child_realm
            node = engine.Node.create(
                host_system=self.__host_system,
                id=add_node.id,
                description=add_node.description,
                **kwargs)
            graph.add_node(node)
            # TODO: schedule setup in a worker thread.
            await realm.setup_node(node)
            realm.update_spec()

        elif mutation_type == 'remove_node':
            remove_node = request.mutation.remove_node
            node = graph.find_node(remove_node.id)
            await node.cleanup(deref=True)
            graph.remove_node(node)
            realm.update_spec()

        elif mutation_type == 'connect_ports':
            connect_ports = request.mutation.connect_ports
            node1 = graph.find_node(connect_ports.src_node_id)
            try:
                port1 = node1.outputs[connect_ports.src_port]
            except KeyError:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node1.id, type(node1).__name__, connect_ports.src_port)
                ).with_traceback(sys.exc_info()[2]) from None

            node2 = graph.find_node(connect_ports.dest_node_id)
            try:
                port2 = node2.inputs[connect_ports.dest_port]
            except KeyError:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node2.id, type(node2).__name__, connect_ports.dest_port)
                ).with_traceback(sys.exc_info()[2]) from None

            port2.connect(port1, connect_ports.type)
            realm.update_spec()

        elif mutation_type == 'disconnect_ports':
            disconnect_ports = request.mutation.disconnect_ports
            node1 = graph.find_node(disconnect_ports.src_node_id)
            node2 = graph.find_node(disconnect_ports.dest_node_id)
            node2.inputs[disconnect_ports.dest_port].disconnect(
                node1.outputs[disconnect_ports.src_port])
            realm.update_spec()

        elif mutation_type == 'set_control_value':
            set_control_value = request.mutation.set_control_value
            realm.set_control_value(
                set_control_value.name,
                set_control_value.value,
                set_control_value.generation)

        elif mutation_type == 'set_plugin_state':
            set_plugin_state = request.mutation.set_plugin_state
            await realm.set_plugin_state(
                set_plugin_state.node_id,
                set_plugin_state.state)

        elif mutation_type == 'set_node_port_properties':
            set_node_port_properties = request.mutation.set_node_port_properties
            node = graph.find_node(set_node_port_properties.node_id)
            node.set_port_properties(set_node_port_properties.port_properties)
            realm.update_spec()

        elif mutation_type == 'set_node_description':
            set_node_description = request.mutation.set_node_description
            node = graph.find_node(set_node_description.node_id)
            if await node.set_description(set_node_description.description):
                realm.update_spec()

        elif mutation_type == 'set_node_parameters':
            set_node_parameters = request.mutation.set_node_parameters
            node = graph.find_node(set_node_parameters.node_id)
            node.set_parameters(set_node_parameters.parameters)

        else:
            raise ValueError(request.mutation)

    def __handle_send_node_messages(
            self,
            session: Session,
            request: audioproc_pb2.SendNodeMessagesRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        realm = self.__engine.get_realm(request.realm)
        for msg in request.messages:
            realm.send_node_message(msg)

    async def __handle_set_host_parameters(
            self,
            session: Session,
            request: host_parameters_pb2.HostParameters,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        await self.__engine.set_host_parameters(request)

    async def __handle_set_backend(
            self,
            session: Session,
            request: audioproc_pb2.SetBackendRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        await self.__engine.set_backend(request.name, request.settings)

    def __handle_set_session_values(
            self,
            session: Session,
            request: audioproc_pb2.SetSessionValuesRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        realm = self.__engine.get_realm(request.realm)
        realm.set_session_values(request.session_values)

    def __handle_update_player_state(
            self,
            session: Session,
            request: player_state_pb2.PlayerState,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        realm = self.__engine.get_realm(request.realm)
        realm.player.update_state(request)

    def __handle_update_project_properties(
            self,
            session: Session,
            request: audioproc_pb2.UpdateProjectPropertiesRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        realm = self.__engine.get_realm(request.realm)
        realm.update_project_properties(request.properties)

    async def __handle_play_file(
            self,
            session: Session,
            request: audioproc_pb2.PlayFileRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        realm = self.__engine.get_realm('root')

        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_db.Builtins.SoundFileDescription)
        node_desc.sound_file.sound_file_path = request.path

        node = engine.Node.create(
            host_system=self.__host_system,
            id=uuid.uuid4().hex,
            description=node_desc)
        realm.graph.add_node(node)
        await realm.setup_node(node)

        sink = realm.graph.find_node('sink')
        sink.inputs['in:left'].connect(node.outputs['out:left'], node_db.PortDescription.AUDIO)
        sink.inputs['in:right'].connect(node.outputs['out:right'], node_db.PortDescription.AUDIO)
        realm.update_spec()

        sound_file_complete_urid = self.__urid_mapper.map(
            "http://noisicaa.odahoda.de/lv2/processor_sound_file#complete")

        complete = asyncio.Event(loop=self.event_loop)

        def handle_notification(notification: engine_notification_pb2.EngineNotification) -> None:
            for node_message in notification.node_messages:
                if node_message.node_id == node.id:
                    msg = lv2.wrap_atom(self.__urid_mapper, node_message.atom)
                    if msg.type_urid == sound_file_complete_urid:
                        complete.set()

        listener = self.__engine.notifications.add(handle_notification)
        await complete.wait()
        listener.remove()

        sink.inputs['in:left'].disconnect(node.outputs['out:left'])
        sink.inputs['in:right'].disconnect(node.outputs['out:right'])
        realm.graph.remove_node(node)
        realm.update_spec()

    async def __handle_create_plugin_ui(
            self,
            session: Session,
            request: audioproc_pb2.CreatePluginUIRequest,
            response: audioproc_pb2.CreatePluginUIResponse,
    ) -> None:
        wid, (width, height) = await self.__engine.create_plugin_ui(request.realm, request.node_id)
        response.wid = wid
        response.width = width
        response.height = height

    async def __handle_delete_plugin_ui(
            self,
            session: Session,
            request: audioproc_pb2.DeletePluginUIRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        await self.__engine.delete_plugin_ui(request.realm, request.node_id)

    async def __handle_profile_audio_thread(
            self,
            session: Session,
            request: audioproc_pb2.ProfileAudioThreadRequest,
            response: audioproc_pb2.ProfileAudioThreadResponse,
    ) -> None:
        path = '/tmp/audio.prof'
        logger.warning("Starting profile of the audio thread...")
        profile.start(path)
        await asyncio.sleep(request.duration, loop=self.event_loop)
        profile.stop()
        logger.warning("Audio thread profile complete. Data written to '%s'.", path)

        argv = ['/usr/bin/google-pprof', '--dot', sys.executable, path]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            loop=self.event_loop)
        dot, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(stderr)
            raise RuntimeError(
                "Command '%s' failed with return code %d" % (' '.join(argv), proc.returncode))

        argv = ['/usr/bin/dot', '-Tsvg']
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            loop=self.event_loop)
        svg, stderr = await proc.communicate(dot)
        if proc.returncode != 0:
            logger.warning(stderr)
            raise RuntimeError(
                "Command '%s' failed with return code %d" % (' '.join(argv), proc.returncode))

        response.svg = svg

    async def __handle_dump(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        if self.__engine is not None:
            logger.error("\n%s", self.__engine.dump())
        else:
            logger.error("No engine.")


class AudioProcSubprocess(core.SubprocessMixin, AudioProcProcess):
    pass
