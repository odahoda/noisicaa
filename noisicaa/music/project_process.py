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
import copy
import logging
import os
import os.path
import pickle
from typing import cast, Any, Optional, Iterator, Sequence, Type, Dict, List, Tuple, TypeVar  # pylint: disable=unused-import

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import node_db
from . import project as project_lib
from . import mutations as mutations_lib
from . import mutations_pb2
from . import commands
from . import commands_pb2
from . import player as player_lib
from . import score_track
from . import render
from . import pmodel  # pylint: disable=unused-import
from . import render_settings_pb2

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    def __init__(self, client_address: str, session_name: str, **kwargs: Any) -> None:
        super().__init__(callback_address=client_address, **kwargs)

        self.session_name = session_name

        self.session_data = {}  # type: Dict[str, Any]
        self.session_data_path = None  # type: str
        self._players = {}  # type: Dict[str, Tuple[core.Listener, player_lib.Player]]

    async def cleanup(self) -> None:
        for listener, p in self._players.values():
            listener.remove()
            await p.cleanup()
        self._players.clear()

        await super().cleanup()

    def get_player(self, player_id: str) -> player_lib.Player:
        return self._players[player_id][1]

    def add_player(self, player: player_lib.Player) -> None:
        listener = player.listeners.add('pipeline_status', self.handle_pipeline_status)
        self._players[player.id] = (listener, player)

    def remove_player(self, player: player_lib.Player) -> None:
        listener = self._players[player.id][0]
        listener.remove()
        del self._players[player.id]

    async def clear_players(self) -> None:
        for listener, player in self._players.values():
            await player.cleanup()
            listener.remove()
        self._players.clear()

    def handle_pipeline_status(self, status: Dict[str, Any]) -> None:
        if 'node_state' in status:
            node_id, state = status['node_state']
            if 'broken' in state:
                self.set_value('pipeline_graph_node/%s/broken' % node_id, state['broken'])

    async def publish_mutations(self, mutations: mutations_pb2.MutationList) -> None:
        assert self.callback_alive

        if not mutations:
            return

        await self.callback('PROJECT_MUTATIONS', mutations)

    async def init_session_data(self, data_dir: str) -> None:
        self.session_data = {}

        if data_dir is not None:
            self.session_data_path = os.path.join(data_dir, 'sessions', self.session_name)
            if not os.path.isdir(self.session_data_path):
                os.makedirs(self.session_data_path)

            checkpoint_path = os.path.join(self.session_data_path, 'checkpoint')
            if os.path.isfile(checkpoint_path):
                with open(checkpoint_path, 'rb') as fp:
                    self.session_data = pickle.load(fp)

        await self.callback('SESSION_DATA_MUTATION', self.session_data)

    def set_value(self, key: str, value: Any, from_client: bool = False) -> None:
        self.set_values({key: value}, from_client=from_client)

    def set_values(self, data: Dict[str, Any], from_client: bool = False) -> None:
        assert self.session_data_path is not None

        changes = {}
        for key, value in data.items():
            if key in self.session_data and self.session_data[key] == value:
                continue
            changes[key] = value

        if not changes:
            return

        self.session_data.update(changes)

        if self.session_data_path is not None:
            with open(os.path.join(self.session_data_path, 'checkpoint'), 'wb') as fp:
                pickle.dump(self.session_data, fp)

        if not from_client:
            self.async_callback('SESSION_DATA_MUTATION', data)


class AudioProcClientImpl(audioproc.AudioProcClientBase):  # pylint: disable=abstract-method
    def __init__(self, event_loop: asyncio.AbstractEventLoop, name: str, tmp_dir: str) -> None:
        super().__init__(event_loop, ipc.Server(event_loop, name, socket_dir=tmp_dir))

    async def setup(self) -> None:
        await self.server.setup()

    async def cleanup(self) -> None:
        await self.server.cleanup()

class AudioProcClient(audioproc.AudioProcClientMixin, AudioProcClientImpl):
    pass


PROJECT = TypeVar('PROJECT', bound=project_lib.BaseProject)

class ProjectProcess(core.SessionHandlerMixin, core.ProcessBase):
    session_cls = Session

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._shutting_down = None

        self.node_db = None  # type: node_db.NodeDBClient
        self.__pool = None  # type: pmodel.Pool
        self.project = None  # type: project_lib.BaseProject
        self.__pending_mutations = mutations_pb2.MutationList()
        self.__mutation_collector = None  # type: mutations_lib.MutationCollector

    async def setup(self) -> None:
        await super().setup()

        self.server.add_command_handler('SHUTDOWN', self.shutdown)
        self.server.add_command_handler('GET_ROOT_ID', self.handle_get_root_id)
        self.server.add_command_handler('CREATE', self.handle_create)
        self.server.add_command_handler('CREATE_INMEMORY', self.handle_create_inmemory)
        self.server.add_command_handler('OPEN', self.handle_open)
        self.server.add_command_handler('CLOSE', self.handle_close)
        self.server.add_command_handler('COMMAND', self.handle_command)
        self.server.add_command_handler('UNDO', self.handle_undo)
        self.server.add_command_handler('REDO', self.handle_redo)
        self.server.add_command_handler('CREATE_PLAYER', self.handle_create_player)
        self.server.add_command_handler('DELETE_PLAYER', self.handle_delete_player)
        self.server.add_command_handler('CREATE_PLUGIN_UI', self.handle_create_plugin_ui)
        self.server.add_command_handler('DELETE_PLUGIN_UI', self.handle_delete_plugin_ui)
        self.server.add_command_handler('UPDATE_PLAYER_STATE', self.handle_update_player_state)
        self.server.add_command_handler('CONTROL_VALUE_CHANGE', self.handle_control_value_change)
        self.server.add_command_handler('PLUGIN_STATE_CHANGE', self.handle_plugin_state_change)
        self.server.add_command_handler('PLAYER_SEND_MESSAGE', self.handle_player_send_message)
        self.server.add_command_handler(
            'RESTART_PLAYER_PIPELINE', self.handle_restart_player_pipeline)
        self.server.add_command_handler('DUMP', self.handle_dump)
        self.server.add_command_handler('RENDER', self.handle_render)
        self.server.add_command_handler('SET_SESSION_VALUES', self.handle_set_session_values)

        node_db_address = await self.manager.call('CREATE_NODE_DB_PROCESS')
        self.node_db = node_db.NodeDBClient(self.event_loop, self.server)
        await self.node_db.setup()
        await self.node_db.connect(node_db_address)

    async def cleanup(self) -> None:
        if self.project is not None:
            await self.__close_project()

        if self.node_db is not None:
            await self.node_db.cleanup()
            self.node_db = None

        await super().cleanup()

    async def publish_mutations(self, mutations: mutations_pb2.MutationList) -> None:
        tasks = []
        for session in self.sessions:
            session = cast(Session, session)
            tasks.append(self.event_loop.create_task(session.publish_mutations(mutations)))
        done, pending = await asyncio.wait(tasks, loop=self.event_loop)
        assert not pending
        for task in done:
            task.result()

    async def session_started(self, session: core.SessionBase) -> None:
        session = cast(Session, session)
        if self.project is not None:
            await session.publish_mutations(self.get_initial_mutations())

    def get_initial_mutations(self) -> mutations_pb2.MutationList:
        mutation_list = mutations_pb2.MutationList()

        for obj in self.project.walk_object_tree():
            op = mutation_list.ops.add()
            op.add_object.object.CopyFrom(obj.proto)

        return mutation_list

    async def send_initial_mutations(self) -> None:
        await self.publish_mutations(self.get_initial_mutations())

    def handle_get_root_id(self, session_id: str) -> Optional[int]:
        self.get_session(session_id)
        if self.project is not None:
            return self.project.id
        return None

    def _create_blank_project(self, project_cls: Type[PROJECT]) -> PROJECT:
        project = self.__pool.create(project_cls, node_db=self.node_db)
        project.add_track(
            project.master_group, 0,
            self.__pool.create(score_track.ScoreTrack, name="Track 1"))
        return project

    async def __close_project(self) -> None:
        assert self.project is not None

        tasks = []
        for session in self.sessions:
            session = cast(Session, session)
            tasks.append(self.event_loop.create_task(session.callback('PROJECT_CLOSED')))
            tasks.append(self.event_loop.create_task(session.clear_players()))
        if tasks:
            done, pending = await asyncio.wait(tasks, loop=self.event_loop)
            assert not pending
            for task in done:
                task.result()

        self.__mutation_collector.stop()
        self.__mutation_collector = None

        self.project.close()

        self.project = None
        self.__pool = None

    async def handle_create(self, session_id: str, path: str) -> int:
        session = cast(Session, self.get_session(session_id))
        assert self.project is None

        self.__pool = project_lib.Pool(project_cls=project_lib.Project)
        self.project = project_lib.Project.create_blank(
            path=path,
            pool=self.__pool,
            node_db=self.node_db)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(self.project.data_dir)
        return self.project.id

    async def handle_create_inmemory(self, session_id: str) -> int:
        session = cast(Session, self.get_session(session_id))
        assert self.project is None

        self.__pool = project_lib.Pool()
        self.project = self._create_blank_project(project_lib.BaseProject)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(None)
        return self.project.id

    async def handle_open(self, session_id: str, path: str) -> int:
        session = cast(Session, self.get_session(session_id))
        assert self.project is None

        self.__pool = project_lib.Pool(project_cls=project_lib.Project)
        self.project = project_lib.Project.open(
            path=path,
            pool=self.__pool,
            node_db=self.node_db)
        await self.send_initial_mutations()
        self.__mutation_collector = mutations_lib.MutationCollector(
            self.__pool, self.__pending_mutations)
        self.__mutation_collector.start()
        await session.init_session_data(self.project.data_dir)
        return self.project.id

    async def handle_close(self) -> None:
        await self.__close_project()

    async def handle_command(self, command: commands_pb2.Command) -> Any:
        assert self.project is not None

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        result = self.project.dispatch_command_proto(command)
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

        return result

    async def handle_undo(self) -> None:
        assert isinstance(self.project, project_lib.Project)

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.project.undo()
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def handle_redo(self) -> None:
        assert isinstance(self.project, project_lib.Project)

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.project.redo()
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def handle_create_player(
            self, session_id: str, *, client_address: str, audioproc_address: str
    ) -> Tuple[str, str]:
        session = cast(Session, self.get_session(session_id))
        assert self.project is not None

        logger.info("Creating audioproc client...")
        audioproc_client = AudioProcClient(self.event_loop, 'player', self.tmp_dir)
        await audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await audioproc_client.connect(audioproc_address)

        realm_name = 'project:%s' % self.project.id
        logger.info("Creating realm '%s'...", realm_name)
        await audioproc_client.create_realm(
            name=realm_name, parent='root',
            enable_player=True, callback_address=self.server.address)

        player = player_lib.Player(
            project=self.project,
            callback_address=client_address,
            event_loop=self.event_loop,
            audioproc_client=audioproc_client,
            realm=realm_name)
        await player.setup()

        session.add_player(player)

        return player.id, player.realm

    async def handle_delete_player(self, session_id: str, player_id: str) -> None:
        session = cast(Session, self.get_session(session_id))
        p = session.get_player(player_id)
        await p.cleanup()

        if p.audioproc_client is not None:
            if p.realm is not None:
                logger.info("Deleting realm '%s'...", p.realm)
                await p.audioproc_client.delete_realm(name=p.realm)
            await p.audioproc_client.disconnect()
            await p.audioproc_client.cleanup()

        session.remove_player(p)

    async def handle_create_plugin_ui(
            self, session_id: str, player_id: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        session = cast(Session, self.get_session(session_id))
        p = session.get_player(player_id)
        return await p.create_plugin_ui(node_id)

    async def handle_delete_plugin_ui(self, session_id: str, player_id: str, node_id: str) -> None:
        session = cast(Session, self.get_session(session_id))
        p = session.get_player(player_id)
        await p.delete_plugin_ui(node_id)

    async def handle_update_player_state(
            self, session_id: str, player_id: str, state: audioproc.PlayerState) -> None:
        session = cast(Session, self.get_session(session_id))
        p = session.get_player(player_id)
        await p.update_state(state)

    async def handle_player_send_message(
            self, session_id: str, player_id: str, msg: Any) -> None:
        session = cast(Session, self.get_session(session_id))
        p = session.get_player(player_id)
        p.send_message(msg)

    async def handle_restart_player_pipeline(self, session_id: str, player_id: str) -> None:
        raise RuntimeError("Not implemented")
        # session = cast(Session, self.get_session(session_id))
        # p = session.get_player(player_id)
        # p.restart_pipeline()

    async def handle_dump(self, session_id: str) -> None:
        assert isinstance(self.project, project_lib.Project)
        self.get_session(session_id)
        logger.info("%s", self.project.proto)

    async def handle_render(
            self, session_id: str, callback_address: str,
            render_settings: render_settings_pb2.RenderSettings) -> None:
        assert self.project is not None
        self.get_session(session_id)

        renderer = render.Renderer(
            project=self.project,
            tmp_dir=self.tmp_dir,
            manager=self.manager,
            event_loop=self.event_loop,
            callback_address=callback_address,
            render_settings=render_settings,
        )
        await renderer.run()

    async def handle_set_session_values(
            self, session_id: str, data: Dict[str, Any]) -> None:
        assert self.project is not None
        session = cast(Session, self.get_session(session_id))
        session.set_values(data, from_client=True)

    async def handle_control_value_change(
            self, realm: str, node_id: int, port_name: str, value: float, generation: int) -> None:
        assert self.project is not None

        logger.info(
            "control_value_change(%s, %s, %s, %f, %d)",
            realm, node_id, port_name, value, generation)

        node = None
        for node in self.project.pipeline_graph_nodes:
            if node.pipeline_node_id == node_id:
                break

        else:
            raise ValueError("Invalid node_id '%s'" % node_id)

        cmd = commands.Command.create(commands_pb2.Command(
            target=node.id,
            set_pipeline_graph_control_value=commands_pb2.SetPipelineGraphControlValue(
                port_name=port_name,
                float_value=value,
                generation=generation)))

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.project.dispatch_command(cmd)
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)

    async def handle_plugin_state_change(
            self, realm: str, node_id: int, state: audioproc.PluginState) -> None:
        assert self.project is not None

        node = None
        for node in self.project.pipeline_graph_nodes:
            if node.pipeline_node_id == node_id:
                break
        else:
            raise ValueError("Invalid node_id '%s'" % node_id)

        cmd = commands.Command.create(commands_pb2.Command(
            target=node.id,
            set_pipeline_graph_plugin_state=commands_pb2.SetPipelineGraphPluginState(
                plugin_state=state)))

        # This block must be atomic, no 'awaits'!
        assert self.__mutation_collector.num_ops == 0
        self.project.dispatch_command(cmd)
        mutations = copy.deepcopy(self.__pending_mutations)
        self.__mutation_collector.clear()

        await self.publish_mutations(mutations)


class ProjectSubprocess(core.SubprocessMixin, ProjectProcess):
    pass
