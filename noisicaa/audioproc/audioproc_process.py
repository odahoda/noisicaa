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
# TODO: pylint-unclean

import functools
import logging
import sys
import uuid

import posix_ipc

from noisicaa import core
from noisicaa import node_db
from noisicaa import lv2
from noisicaa import host_system

from . import engine
from . import mutations

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    def __init__(self, client_address, flags, **kwargs):
        super().__init__(callback_address=client_address, **kwargs)

        self.__flags = flags or set()
        self.__pending_mutations = []
        self.owned_realms = set()

    # async def setup(self):
    #     await super().setup()

        # Send initial mutations to build up the current pipeline
        # state.
        # TODO: reanimate
        #     for node in self.__engine.nodes:
        #         mutation = mutations.AddNode(node)
        #         session.publish_mutation(mutation)
        #     for node in self.__engine.nodes:
        #         for port in node.inputs.values():
        #             for upstream_port in port.inputs:
        #                 mutation = mutations.ConnectPorts(
        #                     upstream_port, port)
        #                 session.publish_mutation(mutation)

    def callback_connected(self):
        while self.__pending_mutations:
            self.publish_mutation(self.__pending_mutations.pop(0))

    def publish_mutation(self, mutation):
        if not self.callback_alive:
            self.__pending_mutations.append(mutation)
            return

        self.async_callback('PIPELINE_MUTATION', mutation)

    def publish_player_state(self, realm, state):
        if realm not in self.owned_realms:
            return

        if not self.callback_alive:
            return

        self.async_callback('PLAYER_STATE', realm, state)

    def publish_status(self, status):
        if not self.callback_alive:
            return

        status = dict(status)

        if 'perf_data' not in self.__flags and 'perf_data' in status:
            del status['perf_data']

        if status:
            self.async_callback('PIPELINE_STATUS', status)


class AudioProcProcess(core.SessionHandlerMixin, core.ProcessBase):

    session_cls = Session

    def __init__(
            self, *,
            shm=None, profile_path=None, block_size=None, sample_rate=None,
            **kwargs):
        super().__init__(**kwargs)
        self.shm_name = shm
        self.profile_path = profile_path
        self.shm = None
        self.__urid_mapper = None
        self.__block_size = block_size
        self.__sample_rate = sample_rate
        self.__host_system = None
        self.__engine = None

    async def setup(self):
        await super().setup()

        self.server.add_command_handler('SHUTDOWN', self.shutdown)
        self.server.add_command_handler('CREATE_REALM', self.__handle_create_realm)
        self.server.add_command_handler('DELETE_REALM', self.__handle_delete_realm)
        self.server.add_command_handler('SET_HOST_PARAMETERS', self.handle_set_host_parameters)
        self.server.add_command_handler('SET_BACKEND', self.handle_set_backend)
        self.server.add_command_handler('SET_BACKEND_PARAMETERS', self.handle_set_backend_parameters)
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
        self.__engine.listeners.add('perf_data', self.perf_data_callback)
        self.__engine.listeners.add('node_state', self.node_state_callback)
        self.__engine.listeners.add('player_state', self.player_state_callback)

        await self.__engine.setup()

    async def cleanup(self):
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

    def publish_mutation(self, mutation):
        for session in self.sessions:
            session.publish_mutation(mutation)

    def publish_status(self, **kwargs):
        for session in self.sessions:
            session.publish_status(kwargs)

    def publish_player_state(self, realm, state):
        for session in self.sessions:
            session.publish_player_state(realm, state)

    async def __handle_create_realm(self, session_id, name, parent, enable_player):
        session = self.get_session(session_id)
        await self.__engine.create_realm(
            name=name,
            parent=parent,
            enable_player=enable_player)
        session.owned_realms.add(name)

    async def __handle_delete_realm(self, session_id, name):
        session = self.get_session(session_id)
        assert name in session.owned_realms
        await self.__engine.delete_realm(name)
        session.owned_realms.remove(name)

    async def handle_pipeline_mutation(self, session_id, realm_name, mutation):
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
            except KeyError as exc:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node1.id, type(node1).__name__, mutation.src_port)
                ).with_traceback(sys.exc_info()[2]) from None

            node2 = graph.find_node(mutation.dest_node)
            try:
                port2 = node2.inputs[mutation.dest_port]
            except KeyError as exc:
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

        elif isinstance(mutation, mutations.SetPortProperty):
            node = graph.find_node(mutation.node)
            port = node.outputs[mutation.port]
            port.set_prop(**mutation.kwargs)

        elif isinstance(mutation, mutations.SetControlValue):
            realm.set_control_value(mutation.name, mutation.value)

        else:
            raise ValueError(type(mutation))

    def handle_send_node_messages(self, session_id, realm_name, messages):
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        for msg in messages.messages:
            realm.send_node_message(msg)

    async def handle_set_host_parameters(self, session_id, parameters):
        self.get_session(session_id)
        await self.__engine.set_host_parameters(**parameters)

    def handle_set_backend(self, session_id, name, parameters):
        self.get_session(session_id)
        self.__engine.set_backend(name, **parameters)

    def handle_set_backend_parameters(self, session_id, parameters):
        self.get_session(session_id)
        self.__engine.set_backend_parameters(**parameters)

    def handle_send_message(self, session_id, msg):
        self.get_session(session_id)
        self.__engine.send_message(msg)

    def handle_update_player_state(self, session_id, realm_name, state):
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        realm.player.update_state(state)

    def handle_update_project_properties(self, session_id, realm_name, properties):
        self.get_session(session_id)
        realm = self.__engine.get_realm(realm_name)
        realm.update_project_properties(**properties)

    def perf_data_callback(self, perf_data):
        self.event_loop.call_soon_threadsafe(
            functools.partial(
                self.publish_status, perf_data=perf_data))

    def node_state_callback(self, realm, node_id, state):
        logger.info('%s %s', node_id, state)
        self.event_loop.call_soon_threadsafe(
            functools.partial(
                self.publish_status, node_state=(realm, node_id, state)))

    def player_state_callback(self, realm, state):
        self.event_loop.call_soon_threadsafe(
            functools.partial(self.publish_player_state, realm, state))

    async def handle_play_file(self, session_id, path):
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

        self.__engine.notification_listener.add(
            node.id,
            functools.partial(self.play_file_done, node_id=node.id))

        return node.id

    def play_file_done(self, msg_type, *, node_id):
        realm = self.__engine.get_realm('root')

        node = realm.graph.find_node(node_id)
        sink = realm.graph.find_node('sink')
        sink.inputs['in:left'].disconnect(node.outputs['out:left'])
        sink.inputs['in:right'].disconnect(node.outputs['out:right'])
        realm.graph.remove_node(node)
        realm.update_spec()

    async def handle_create_plugin_ui(self, session_id, realm_name, node_id):
        self.get_session(session_id)
        return await self.__engine.create_plugin_ui(realm_name, node_id)

    async def handle_delete_plugin_ui(self, session_id, realm_name, node_id):
        self.get_session(session_id)
        return await self.__engine.delete_plugin_ui(realm_name, node_id)

    def handle_dump(self, session_id):
        self.__engine.dump()


class AudioProcSubprocess(core.SubprocessMixin, AudioProcProcess):
    pass
