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

import asyncio
import functools
import logging
import sys
import time
import uuid
from typing import cast, Any, Optional, Dict, Set, Tuple

import posix_ipc

from noisicaa import core
from noisicaa import node_db
from noisicaa import lv2
from noisicaa import host_system
from .public import engine_notification_pb2
from .public import player_state_pb2
from .public import processor_message_pb2
from . import engine
from . import mutations

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    async_connect = False

    def __init__(self, client_address: str, flags: Set, **kwargs: Any) -> None:
        super().__init__(callback_address=client_address, **kwargs)

        self.__flags = flags or set()
        self.owned_realms = set()  # type: Set[str]

        self.__shutdown = False
        self.__notification_pusher_task = None  # type: asyncio.Task
        self.__notification_available = None  # type: asyncio.Event
        self.__pending_notification = engine_notification_pb2.EngineNotification()

    async def setup(self) -> None:
        await super().setup()

        self.__shutdown = False
        self.__notification_available = asyncio.Event(loop=self.event_loop)
        self.__notification_pusher_task = self.event_loop.create_task(
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
                await asyncio.sleep(delay, loop=self.event_loop)

    def callback_connected(self) -> None:
        pass

    def publish_engine_notification(self, msg: engine_notification_pb2.EngineNotification) -> None:
        # TODO: filter out message for not owned realms
        self.__pending_notification.MergeFrom(msg)
        self.__notification_available.set()


class AudioProcProcess(core.SessionHandlerMixin, core.ProcessBase):
    session_cls = Session

    def __init__(
            self, *,
            shm: Optional[str] = None, profile_path: Optional[str] = None,
            block_size: Optional[int] = None, sample_rate: Optional[int] = None,
            **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.shm_name = shm
        self.profile_path = profile_path
        self.shm = None  # type: Optional[posix_ipc.SharedMemory]
        self.__urid_mapper = None  # type: lv2.ProxyURIDMapper
        self.__block_size = block_size
        self.__sample_rate = sample_rate
        self.__host_system = None  # type: host_system.HostSystem
        self.__engine = None  # type: engine.Engine

    async def setup(self) -> None:
        await super().setup()

        self.server.add_command_handler('SHUTDOWN', self.shutdown)
        self.server.add_command_handler('CREATE_REALM', self.__handle_create_realm)
        self.server.add_command_handler('DELETE_REALM', self.__handle_delete_realm)
        self.server.add_command_handler('SET_HOST_PARAMETERS', self.handle_set_host_parameters)
        self.server.add_command_handler('SET_BACKEND', self.handle_set_backend)
        self.server.add_command_handler(
            'SET_BACKEND_PARAMETERS', self.handle_set_backend_parameters)
        self.server.add_command_handler('SEND_MESSAGE', self.handle_send_message)
        self.server.add_command_handler('PLAY_FILE', self.handle_play_file)
        self.server.add_command_handler('PIPELINE_MUTATION', self.handle_pipeline_mutation)
        self.server.add_command_handler('SEND_NODE_MESSAGES', self.handle_send_node_messages)
        self.server.add_command_handler('UPDATE_PLAYER_STATE', self.handle_update_player_state)
        self.server.add_command_handler(
            'UPDATE_PROJECT_PROPERTIES', self.handle_update_project_properties)
        self.server.add_command_handler('CREATE_PLUGIN_UI', self.handle_create_plugin_ui)
        self.server.add_command_handler('DELETE_PLUGIN_UI', self.handle_delete_plugin_ui)
        self.server.add_command_handler('DUMP', self.handle_dump)

        if self.shm_name is not None:
            self.shm = posix_ipc.SharedMemory(self.shm_name)

        urid_mapper_address = await self.manager.call('CREATE_URID_MAPPER_PROCESS')

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
            shm=self.shm,
            profile_path=self.profile_path)
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
        for session in self.sessions:
            cast(Session, session).publish_engine_notification(msg)

    async def __handle_create_realm(
            self, session_id: str, name: str, parent: str, enable_player: bool,
            callback_address: str
    ) -> None:
        session = cast(Session, self.get_session(session_id))
        await self.__engine.create_realm(
            name=name,
            parent=parent,
            enable_player=enable_player,
            callback_address=callback_address)
        session.owned_realms.add(name)

    async def __handle_delete_realm(self, session_id: str, name: str) -> None:
        session = cast(Session, self.get_session(session_id))
        assert name in session.owned_realms
        await self.__engine.delete_realm(name)
        session.owned_realms.remove(name)

    async def handle_pipeline_mutation(
            self, session_id: str, realm_name: str, mutation: mutations.Mutation) -> None:
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        graph = realm.graph

        if isinstance(mutation, mutations.AddNode):
            logger.info("AddNode():\n%s", mutation.description)
            node = engine.Node.create(
                host_system=self.__host_system,
                description=mutation.description,
                **mutation.args)
            graph.add_node(node)
            # TODO: schedule setup in a worker thread.
            await realm.setup_node(node)
            realm.update_spec()

        elif isinstance(mutation, mutations.RemoveNode):
            node = graph.find_node(mutation.node_id)
            await node.cleanup(deref=True)
            graph.remove_node(node)
            realm.update_spec()

        elif isinstance(mutation, mutations.ConnectPorts):
            node1 = graph.find_node(mutation.src_node)
            try:
                port1 = node1.outputs[mutation.src_port]
            except KeyError:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node1.id, type(node1).__name__, mutation.src_port)
                ).with_traceback(sys.exc_info()[2]) from None

            node2 = graph.find_node(mutation.dest_node)
            try:
                port2 = node2.inputs[mutation.dest_port]
            except KeyError:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node2.id, type(node2).__name__, mutation.dest_port)
                ).with_traceback(sys.exc_info()[2]) from None
            port2.connect(port1)
            realm.update_spec()

        elif isinstance(mutation, mutations.DisconnectPorts):
            node1 = graph.find_node(mutation.src_node)
            node2 = graph.find_node(mutation.dest_node)
            node2.inputs[mutation.dest_port].disconnect(node1.outputs[mutation.src_port])
            realm.update_spec()

        elif isinstance(mutation, mutations.SetControlValue):
            realm.set_control_value(mutation.name, mutation.value, mutation.generation)

        elif isinstance(mutation, mutations.SetPluginState):
            await realm.set_plugin_state(mutation.node, mutation.state)

        else:
            raise ValueError(type(mutation))

    def handle_send_node_messages(
            self, session_id: str, realm_name: str,
            messages: processor_message_pb2.ProcessorMessageList) -> None:
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        for msg in messages.messages:
            realm.send_node_message(msg)

    async def handle_set_host_parameters(self, session_id: str, parameters: Any) -> None:
        self.get_session(session_id)
        await self.__engine.set_host_parameters(**parameters)

    def handle_set_backend(self, session_id: str, name: str, parameters: Dict[str, Any]) -> None:
        self.get_session(session_id)
        self.__engine.set_backend(name, **parameters)

    def handle_set_backend_parameters(self, session_id: str, parameters: Dict[str, Any]) -> None:
        self.get_session(session_id)
        self.__engine.set_backend_parameters(**parameters)

    def handle_send_message(self, session_id: str, msg: bytes) -> None:
        self.get_session(session_id)
        self.__engine.send_message(msg)

    def handle_update_player_state(
            self, session_id: str, state: player_state_pb2.PlayerState) -> None:
        self.get_session(session_id)
        realm = self.__engine.get_realm(state.realm)
        realm.player.update_state(state)

    def handle_update_project_properties(
            self, session_id: str, realm_name: str, properties: Dict[str, Any]) -> None:
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        realm.update_project_properties(**properties)

    async def handle_play_file(self, session_id: str, path: str) -> str:
        self.get_session(session_id)

        realm = self.__engine.get_realm('root')

        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_db.Builtins.SoundFileDescription)
        node_desc.sound_file.sound_file_path = path

        node = engine.Node.create(
            host_system=self.__host_system,
            id=uuid.uuid4().hex,
            description=node_desc)
        realm.graph.add_node(node)
        await realm.setup_node(node)

        sink = realm.graph.find_node('sink')
        sink.inputs['in:left'].connect(node.outputs['out:left'])
        sink.inputs['in:right'].connect(node.outputs['out:right'])
        realm.update_spec()

        self.__engine.add_notification_listener(
            node.id,
            functools.partial(self.play_file_done, node_id=node.id))

        return node.id

    def play_file_done(self, msg_type: str, *, node_id: str) -> None:
        realm = self.__engine.get_realm('root')

        node = realm.graph.find_node(node_id)
        sink = realm.graph.find_node('sink')
        sink.inputs['in:left'].disconnect(node.outputs['out:left'])
        sink.inputs['in:right'].disconnect(node.outputs['out:right'])
        realm.graph.remove_node(node)
        realm.update_spec()

    async def handle_create_plugin_ui(
            self, session_id: str, realm_name: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        self.get_session(session_id)
        return await self.__engine.create_plugin_ui(realm_name, node_id)

    async def handle_delete_plugin_ui(self, session_id: str, realm_name: str, node_id: str) -> None:
        self.get_session(session_id)
        return await self.__engine.delete_plugin_ui(realm_name, node_id)

    def handle_dump(self, session_id: str) -> None:
        self.__engine.dump()


class AudioProcSubprocess(core.SubprocessMixin, AudioProcProcess):
    pass
