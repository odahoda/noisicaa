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
import copy
import logging
import traceback
import typing
from typing import Any, Dict, Type, Iterable, TypeVar

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.core import session_data_pb2
from noisicaa import audioproc
from noisicaa import lv2
from noisicaa import node_db
from noisicaa import editor_main_pb2
from noisicaa.builtin_nodes import server_registry
from . import project_process_pb2
from . import project_process_context
from . import project as project_lib
from . import mutations as mutations_lib
from . import mutations_pb2
from . import commands
from . import commands_pb2
from . import player as player_lib
from . import render
from . import session_value_store

if typing.TYPE_CHECKING:
    from . import pmodel

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

        assert start_session_request.HasField('session_name')
        self.session_values = session_value_store.SessionValueStore(
            event_loop, start_session_request.session_name)

        self.__players = {}  # type: Dict[str, player_lib.Player]

    async def cleanup(self) -> None:
        await self.clear_players()
        await super().cleanup()

    def get_player(self, player_id: str) -> player_lib.Player:
        return self.__players[player_id]

    async def add_player(self, player: player_lib.Player) -> None:
        self.__players[player.id] = player

    def remove_player(self, player: player_lib.Player) -> None:
        del self.__players[player.id]

    async def clear_players(self) -> None:
        players = list(self.__players.values())
        self.__players.clear()

        for player in players:
            await player.cleanup()

    async def publish_mutations(self, mutations: mutations_pb2.MutationList) -> None:
        assert self.callback_alive

        if not mutations:
            return

        await self.callback('PROJECT_MUTATIONS', mutations)

    async def init_session_data(self, data_dir: str) -> None:
        await self.session_values.init(data_dir)

        await self.callback(
            'SESSION_DATA_MUTATION',
            project_process_pb2.SessionDataMutation(session_values=self.session_values.values()))

    async def set_values(
            self, session_values: Iterable[session_data_pb2.SessionValue],
            from_client: bool = False
    ) -> None:
        await self.session_values.set_values(session_values)

        if not from_client:
            self.async_callback(
                'SESSION_DATA_MUTATION',
                project_process_pb2.SessionDataMutation(session_values=session_values))


PROJECT = TypeVar('PROJECT', bound=project_lib.BaseProject)

class ProjectProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._shutting_down = None

        self.__main_endpoint = None  # type: ipc.ServerEndpointWithSessions[Session]
        self.__ctxt = project_process_context.ProjectProcessContext()
        self.__pending_mutations = mutations_pb2.MutationList()
        self.__mutation_collector = None  # type: mutations_lib.MutationCollector

    async def setup(self) -> None:
        await super().setup()

        self.__main_endpoint = ipc.ServerEndpointWithSessions(
            'main', Session,
            session_started=self.__session_started)
        self.__main_endpoint.add_handler(
            'GET_ROOT_ID', self.__handle_get_root_id,
            empty_message_pb2.EmptyMessage, project_process_pb2.ProjectId)
        self.__main_endpoint.add_handler(
            'CREATE', self.__handle_create,
            project_process_pb2.CreateRequest, project_process_pb2.ProjectId)
        self.__main_endpoint.add_handler(
            'CREATE_INMEMORY', self.__handle_create_inmemory,
            empty_message_pb2.EmptyMessage, project_process_pb2.ProjectId)
        self.__main_endpoint.add_handler(
            'OPEN', self.__handle_open,
            project_process_pb2.OpenRequest, project_process_pb2.ProjectId)
        self.__main_endpoint.add_handler(
            'CLOSE', self.__handle_close,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'COMMAND_SEQUENCE', self.__handle_command_sequence,
            commands_pb2.CommandSequence, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'UNDO', self.__handle_undo,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'REDO', self.__handle_redo,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'CREATE_PLAYER', self.__handle_create_player,
            project_process_pb2.CreatePlayerRequest, project_process_pb2.CreatePlayerResponse)
        self.__main_endpoint.add_handler(
            'DELETE_PLAYER', self.__handle_delete_player,
            project_process_pb2.DeletePlayerRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'CREATE_PLUGIN_UI', self.__handle_create_plugin_ui,
            project_process_pb2.CreatePluginUIRequest, project_process_pb2.CreatePluginUIResponse)
        self.__main_endpoint.add_handler(
            'DELETE_PLUGIN_UI', self.__handle_delete_plugin_ui,
            project_process_pb2.DeletePluginUIRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'UPDATE_PLAYER_STATE', self.__handle_update_player_state,
            project_process_pb2.UpdatePlayerStateRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'DUMP', self.__handle_dump,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'RENDER', self.__handle_render,
            project_process_pb2.RenderRequest, empty_message_pb2.EmptyMessage)
        self.__main_endpoint.add_handler(
            'SET_SESSION_VALUES', self.__handle_set_session_values,
            project_process_pb2.SetSessionValuesRequest, empty_message_pb2.EmptyMessage)
        server_registry.register_ipc_handlers(self.__ctxt, self.__main_endpoint)
        await self.server.add_endpoint(self.__main_endpoint)

        cb_endpoint = ipc.ServerEndpoint('project_cb')
        cb_endpoint.add_handler(
            'CONTROL_VALUE_CHANGE', self.__handle_control_value_change,
            audioproc.ControlValueChange, empty_message_pb2.EmptyMessage)
        cb_endpoint.add_handler(
            'PLUGIN_STATE_CHANGE', self.__handle_plugin_state_change,
            audioproc.PluginStateChange, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(cb_endpoint)

        create_node_db_response = editor_main_pb2.CreateProcessResponse()
        await self.manager.call(
            'CREATE_NODE_DB_PROCESS', None, create_node_db_response)
        node_db_address = create_node_db_response.address

        self.__ctxt.node_db = node_db.NodeDBClient(self.event_loop, self.server)
        await self.__ctxt.node_db.setup()
        await self.__ctxt.node_db.connect(node_db_address)

        create_urid_mapper_response = editor_main_pb2.CreateProcessResponse()
        await self.manager.call(
            'CREATE_URID_MAPPER_PROCESS', None, create_urid_mapper_response)
        urid_mapper_address = create_urid_mapper_response.address

        self.__ctxt.urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=self.tmp_dir)
        await self.__ctxt.urid_mapper.setup(self.event_loop)

    async def cleanup(self) -> None:
        if self.__ctxt.project is not None:
            await self.__close_project()

        if self.__ctxt.node_db is not None:
            await self.__ctxt.node_db.cleanup()
            self.__ctxt.node_db = None

        if self.__ctxt.urid_mapper is not None:
            await self.__ctxt.urid_mapper.cleanup(self.event_loop)
            self.__ctxt.urid_mapper = None

        await super().cleanup()

    async def publish_mutations(self, mutations: mutations_pb2.MutationList) -> None:
        tasks = []
        for session in self.__main_endpoint.sessions:
            tasks.append(self.event_loop.create_task(session.publish_mutations(mutations)))
        done, pending = await asyncio.wait(tasks, loop=self.event_loop)
        assert not pending
        for task in done:
            task.result()

    async def __session_started(self, session: Session) -> None:
        if self.__ctxt.project is not None:
            await session.publish_mutations(self.get_initial_mutations())

    def get_initial_mutations(self) -> mutations_pb2.MutationList:
        mutation_list = mutations_pb2.MutationList()

        for obj in self.__ctxt.project.walk_object_tree():
            op = mutation_list.ops.add()
            op.add_object.object.CopyFrom(obj.proto)

        return mutation_list

    async def send_initial_mutations(self) -> None:
        await self.publish_mutations(self.get_initial_mutations())

    def __handle_get_root_id(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: project_process_pb2.ProjectId,
    ) -> None:
        if self.__ctxt.project is not None:
            response.project_id = self.__ctxt.project.id

    def _create_blank_project(self, project_cls: Type[PROJECT]) -> PROJECT:
        project = self.__ctxt.pool.create(project_cls, node_db=self.__ctxt.node_db)
        self.__ctxt.pool.set_root(project)
        return project

    async def __close_project(self) -> None:
        assert self.__ctxt.project is not None

        tasks = []
        for session in self.__main_endpoint.sessions:
            tasks.append(self.event_loop.create_task(session.callback('PROJECT_CLOSED')))
            tasks.append(self.event_loop.create_task(session.clear_players()))
        if tasks:
            done, pending = await asyncio.wait(tasks, loop=self.event_loop)
            assert not pending
            for task in done:
                try:
                    task.result()
                except ipc.ConnectionClosed:
                    pass

        if self.__mutation_collector is not None:
            self.__mutation_collector.stop()
            self.__mutation_collector = None

        self.__ctxt.project.close()

        self.__ctxt.project = None
        self.__ctxt.pool = None

    async def __handle_create(
            self,
            session: Session,
            request: project_process_pb2.CreateRequest,
            response: project_process_pb2.ProjectId,
    ) -> None:
        assert self.__ctxt.project is None

        self.__ctxt.pool = project_lib.Pool(project_cls=project_lib.Project)
        self.__ctxt.project = project_lib.Project.create_blank(
            path=request.path,
            pool=self.__ctxt.pool,
            node_db=self.__ctxt.node_db)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__ctxt.pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(self.__ctxt.project.data_dir)
        response.project_id = self.__ctxt.project.id

    async def __handle_create_inmemory(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: project_process_pb2.ProjectId,
    ) -> None:
        assert self.__ctxt.project is None

        self.__ctxt.pool = project_lib.Pool()
        self.__ctxt.project = self._create_blank_project(project_lib.BaseProject)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__ctxt.pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(None)
        response.project_id = self.__ctxt.project.id

    async def __handle_open(
            self,
            session: Session,
            request: project_process_pb2.OpenRequest,
            response: project_process_pb2.ProjectId,
    ) -> None:
        assert self.__ctxt.project is None

        self.__ctxt.pool = project_lib.Pool(project_cls=project_lib.Project)
        self.__ctxt.project = project_lib.Project.open(
            path=request.path,
            pool=self.__ctxt.pool,
            node_db=self.__ctxt.node_db)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__ctxt.pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(self.__ctxt.project.data_dir)
        response.project_id = self.__ctxt.project.id

    async def __handle_close(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        await self.__close_project()

    async def __handle_command_sequence(
            self,
            session: Session,
            request: commands_pb2.CommandSequence,
            response: empty_message_pb2.EmptyMessage,
    ) -> Any:
        assert self.__ctxt.project is not None

        try:
            # This block must be atomic, no 'awaits'!
            assert self.__mutation_collector.num_ops == 0
            self.__ctxt.project.dispatch_command_sequence_proto(request)
            mutations = copy.deepcopy(self.__pending_mutations)
            self.__mutation_collector.clear()
        except commands.ClientError:
            raise
        except Exception:
            logger.error(
                "Exception while handling command sequence\n%s\n%s",
                request, traceback.format_exc())
            self.start_shutdown()
            raise ipc.CloseConnection

        await self.publish_mutations(mutations)

    async def __handle_undo(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        assert isinstance(self.__ctxt.project, project_lib.Project)

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.__ctxt.project.undo()
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def __handle_redo(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        assert isinstance(self.__ctxt.project, project_lib.Project)

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.__ctxt.project.redo()
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def __handle_create_player(
            self,
            session: Session,
            request: project_process_pb2.CreatePlayerRequest,
            response: project_process_pb2.CreatePlayerResponse
    ) -> None:
        assert self.__ctxt.project is not None

        logger.info("Creating audioproc client...")
        audioproc_client = audioproc.AudioProcClient(
            self.event_loop, self.server, self.__ctxt.urid_mapper)
        await audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await audioproc_client.connect(request.audioproc_address)

        realm_name = 'project:%s' % self.__ctxt.project.id
        logger.info("Creating realm '%s'...", realm_name)
        await audioproc_client.create_realm(
            name=realm_name, parent='root',
            enable_player=True, callback_address=self.server.endpoint_address('project_cb'))

        player = player_lib.Player(
            project=self.__ctxt.project,
            callback_address=request.client_address,
            event_loop=self.event_loop,
            audioproc_client=audioproc_client,
            realm=realm_name,
            session_values=session.session_values)
        await player.setup()

        await session.add_player(player)

        response.id = player.id
        response.realm = player.realm

    async def __handle_delete_player(
            self,
            session: Session,
            request: project_process_pb2.DeletePlayerRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        p = session.get_player(request.player_id)
        await p.cleanup()

        if p.audioproc_client is not None:
            if p.realm is not None:
                logger.info("Deleting realm '%s'...", p.realm)
                await p.audioproc_client.delete_realm(name=p.realm)
            await p.audioproc_client.disconnect()
            await p.audioproc_client.cleanup()

        session.remove_player(p)

    async def __handle_create_plugin_ui(
            self,
            session: Session,
            request: project_process_pb2.CreatePluginUIRequest,
            response: project_process_pb2.CreatePluginUIResponse
    ) -> None:
        p = session.get_player(request.player_id)
        wid, (width, height) = await p.create_plugin_ui(request.node_id)
        response.wid = wid
        response.width = width
        response.height = height

    async def __handle_delete_plugin_ui(
            self,
            session: Session,
            request: project_process_pb2.DeletePluginUIRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        p = session.get_player(request.player_id)
        await p.delete_plugin_ui(request.node_id)

    async def __handle_update_player_state(
            self,
            session: Session,
            request: project_process_pb2.UpdatePlayerStateRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        p = session.get_player(request.player_id)
        await p.update_state(request.state)

    async def __handle_dump(
            self,
            session: Session,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert isinstance(self.__ctxt.project, project_lib.Project)
        logger.info("%s", self.__ctxt.project.proto)

    async def __handle_render(
            self,
            session: Session,
            request: project_process_pb2.RenderRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__ctxt.project is not None

        renderer = render.Renderer(
            project=self.__ctxt.project,
            tmp_dir=self.tmp_dir,
            server=self.server,
            manager=self.manager,
            event_loop=self.event_loop,
            callback_address=request.callback_address,
            render_settings=request.settings,
            urid_mapper=self.__ctxt.urid_mapper,
        )
        await renderer.run()

    async def __handle_set_session_values(
            self,
            session: Session,
            request: project_process_pb2.SetSessionValuesRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__ctxt.project is not None
        await session.set_values(request.session_values, from_client=True)

    async def __handle_control_value_change(
            self,
            request: audioproc.ControlValueChange,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__ctxt.project is not None

        logger.info(
            "control_value_change(%s, %s, %s, %f, %d)",
            request.realm, request.node_id,
            request.value.name, request.value.value, request.value.generation)

        node = None
        for node in self.__ctxt.project.nodes:
            if node.pipeline_node_id == request.node_id:
                break

        else:
            raise ValueError("Invalid node_id '%s'" % request.node_id)

        seq = commands_pb2.CommandSequence(
            commands=[commands_pb2.Command(
                command='update_node',
                update_node=commands_pb2.UpdateNode(
                    node_id=node.id,
                    set_control_value=request.value))])

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.__ctxt.project.dispatch_command_sequence_proto(seq)
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def __handle_plugin_state_change(
            self,
            request: audioproc.PluginStateChange,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__ctxt.project is not None

        node = None
        for node in self.__ctxt.project.nodes:
            if node.pipeline_node_id == request.node_id:
                break
        else:
            raise ValueError("Invalid node_id '%s'" % request.node_id)

        seq = commands_pb2.CommandSequence(
            commands=[commands_pb2.Command(
                command='update_node',
                update_node=commands_pb2.UpdateNode(
                    node_id=node.id,
                    set_plugin_state=request.state))])

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.__ctxt.project.dispatch_command_sequence_proto(seq)
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)


class ProjectSubprocess(core.SubprocessMixin, ProjectProcess):
    pass
