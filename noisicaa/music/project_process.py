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

import asyncio
import logging
import os
import os.path
import pickle
import pprint

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import node_db

from . import project
from . import mutations
from . import commands
from . import player
from . import state
from . import score_track
from . import render

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    def __init__(self, client_address, session_name, **kwargs):
        super().__init__(callback_address=client_address, **kwargs)

        self.session_name = session_name

        self.session_data = {}
        self.session_data_path = None
        self._players = {}

    async def cleanup(self):
        for listener, p in self._players.values():
            listener.remove()
            await p.cleanup()
        self._players.clear()

        await super().cleanup()

    def get_player(self, player_id):
        return self._players[player_id][1]

    def add_player(self, player):
        listener = player.listeners.add('pipeline_status', self.handle_pipeline_status)
        self._players[player.id] = (listener, player)

    def remove_player(self, player):
        listener = self._players[player.id][0]
        listener.remove()
        del self._players[player.id]

    async def clear_players(self):
        for player_id, (listener, player) in self._players.items():
            await player.cleanup()
            listener.remove()
        self._players.clear()

    def handle_pipeline_status(self, status):
        if 'node_state' in status:
            node_id, state = status['node_state']
            if 'broken' in state:
                self.set_value('pipeline_graph_node/%s/broken' % node_id, state['broken'])

    async def publish_mutations(self, mutations):
        assert self.callback_alive

        if not mutations:
            return

        logger.info(
            "Publish mutations:\n%s",
            '\n'.join(str(mutation) for mutation in mutations))

        await self.callback('PROJECT_MUTATIONS', mutations)

    async def init_session_data(self, data_dir):
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

    def set_value(self, key, value, from_client=False):
        self.set_values({key: value}, from_client=from_client)

    def set_values(self, data, from_client=False):
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


class AudioProcClientImpl(object):
    def __init__(self, event_loop, name, tmp_dir):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(event_loop, name, socket_dir=tmp_dir)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()

class AudioProcClient(audioproc.AudioProcClientMixin, AudioProcClientImpl):
    pass


class ProjectProcess(core.SessionHandlerMixin, core.ProcessBase):
    session_cls = Session

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._shutting_down = None

        self.node_db = None
        self.project = None
        self.pending_mutations = []

    async def setup(self):
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
        self.server.add_command_handler('SERIALIZE', self.handle_serialize)
        self.server.add_command_handler('CREATE_PLAYER', self.handle_create_player)
        self.server.add_command_handler('DELETE_PLAYER', self.handle_delete_player)
        self.server.add_command_handler('CREATE_PLUGIN_UI', self.handle_create_plugin_ui)
        self.server.add_command_handler('DELETE_PLUGIN_UI', self.handle_delete_plugin_ui)
        self.server.add_command_handler(
            'GET_PLAYER_AUDIOPROC_ADDRESS',
            self.handle_get_player_audioproc_address)
        self.server.add_command_handler('UPDATE_PLAYER_STATE', self.handle_update_player_state)
        self.server.add_command_handler('PLAYER_SEND_MESSAGE', self.handle_player_send_message)
        self.server.add_command_handler(
            'RESTART_PLAYER_PIPELINE', self.handle_restart_player_pipeline)
        self.server.add_command_handler('DUMP', self.handle_dump)
        self.server.add_command_handler('RENDER', self.handle_render)
        self.server.add_command_handler('SET_SESSION_VALUES', self.handle_set_session_values)

        node_db_address = await self.manager.call(
            'CREATE_NODE_DB_PROCESS')
        self.node_db = node_db.NodeDBClient(self.event_loop, self.server)
        await self.node_db.setup()
        await self.node_db.connect(node_db_address)

    async def cleanup(self):
        if self.node_db is not None:
            await self.node_db.cleanup()
            self.node_db = None
        await super().cleanup()

    def handle_model_change(self, obj, change):
        logger.info("Model change on %s: %s", obj, change)

        if isinstance(change, core.PropertyValueChange):
            if (change.new_value is not None
                and isinstance(change.new_value, state.StateBase)
                and not isinstance(
                    obj.get_property(change.prop_name),
                    core.ObjectReferenceProperty)):
                for mutation in self.add_object_mutations(
                        change.new_value):
                    self.pending_mutations.append(mutation)

            self.pending_mutations.append(
                mutations.SetProperties(obj, [change.prop_name]))

        elif isinstance(change, core.PropertyListInsert):
            if isinstance(change.new_value, state.StateBase):
                for mutation in self.add_object_mutations(
                        change.new_value):
                    self.pending_mutations.append(mutation)

            self.pending_mutations.append(
                mutations.ListInsert(
                    obj, change.prop_name, change.index, change.new_value))

        elif isinstance(change, core.PropertyListDelete):
            self.pending_mutations.append(
                mutations.ListDelete(
                    obj, change.prop_name, change.index))

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    async def publish_mutations(self, mutations):
        tasks = []
        for session in self.sessions:
            tasks.append(self.event_loop.create_task(
                session.publish_mutations(mutations)))
        await asyncio.wait(tasks, loop=self.event_loop)

    async def session_started(self, session):
        if self.project is not None:
            await session.publish_mutations(
                list(self.add_object_mutations(self.project)))

    def add_object_mutations(self, obj):
        for prop in obj.list_properties():
            if prop.name == 'id':
                continue

            if isinstance(prop, core.ObjectProperty):
                child = getattr(obj, prop.name)
                if child is not None:
                    yield from self.add_object_mutations(child)

            elif isinstance(prop, core.ObjectListProperty):
                for child in getattr(obj, prop.name):
                    assert child is not None
                    yield from self.add_object_mutations(child)

        yield mutations.AddObject(obj)

    async def send_initial_mutations(self):
        await self.publish_mutations(
            list(self.add_object_mutations(self.project)))

    def handle_get_root_id(self, session_id):
        self.get_session(session_id)
        if self.project is not None:
            return self.project.id
        return None

    def _create_blank_project(self, project_cls):
        project = project_cls(node_db=self.node_db)
        project.add_track(project.master_group, 0, score_track.ScoreTrack(name="Track 1"))
        return project

    async def handle_create(self, session_id, path):
        session = self.get_session(session_id)
        assert self.project is None
        self.project = self._create_blank_project(project.Project)
        self.project.create(path)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        await session.init_session_data(self.project.data_dir)
        return self.project.id

    async def handle_create_inmemory(self, session_id):
        session = self.get_session(session_id)
        assert self.project is None
        self.project = self._create_blank_project(project.BaseProject)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        await session.init_session_data(None)
        return self.project.id

    async def handle_open(self, session_id, path):
        session = self.get_session(session_id)
        assert self.project is None
        self.project = project.Project(node_db=self.node_db)
        self.project.open(path)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        await session.init_session_data(self.project.data_dir)
        return self.project.id

    async def handle_close(self):
        assert self.project is not None

        tasks = []
        for session in self.sessions:
            tasks.append(self.event_loop.create_task(session.callback('PROJECT_CLOSED')))
            tasks.append(self.event_loop.create_task(session.clear_players()))
        await asyncio.wait(tasks, loop=self.event_loop)

        self.project.close()
        self.project = None

    async def handle_command(self, target, command, kwargs):
        assert self.project is not None

        # This block must be atomic, no 'awaits'!
        assert not self.pending_mutations
        cmd = commands.Command.create(command, **kwargs)
        result = self.project.dispatch_command(target, cmd)
        mutations = self.pending_mutations[:]
        self.pending_mutations.clear()

        await self.publish_mutations(mutations)

        return result

    async def handle_undo(self):
        assert self.project is not None

        # This block must be atomic, no 'awaits'!
        assert not self.pending_mutations
        self.project.undo()
        mutations = self.pending_mutations[:]
        self.pending_mutations.clear()

        await self.publish_mutations(mutations)

    async def handle_redo(self):
        assert self.project is not None

        # This block must be atomic, no 'awaits'!
        assert not self.pending_mutations
        self.project.redo()
        mutations = self.pending_mutations[:]
        self.pending_mutations.clear()

        await self.publish_mutations(mutations)

    async def handle_serialize(self, session_id, obj_id):
        assert self.project is not None

        obj = self.project.get_object(obj_id)
        return self.project.serialize_object(obj)

    async def handle_create_player(
            self, session_id, *, client_address, audioproc_address):
        session = self.get_session(session_id)
        assert self.project is not None

        logger.info("Creating audioproc client...")
        audioproc_client = AudioProcClient(self.event_loop, 'player', self.tmp_dir)
        await audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await audioproc_client.connect(audioproc_address)

        realm_name = 'project:%s' % self.project.id
        logger.info("Creating realm '%s'...", realm_name)
        await audioproc_client.create_realm(name=realm_name, parent='root', enable_player=True)

        p = player.Player(
            project=self.project,
            callback_address=client_address,
            event_loop=self.event_loop,
            audioproc_client=audioproc_client,
            realm=realm_name)
        await p.setup()

        session.add_player(p)

        return p.id, p.realm

    async def handle_get_player_audioproc_address(
        self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        return p.audioproc_address

    async def handle_delete_player(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        await p.cleanup()

        if p.audioproc_client is not None:
            if p.realm is not None:
                logger.info("Deleting realm '%s'...", p.realm)
                await p.audioproc_client.delete_realm(name=p.realm)
            await p.audioproc_client.disconnect()
            await p.audioproc_client.cleanup()

        session.remove_player(p)

    async def handle_create_plugin_ui(self, session_id, player_id, node_id):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        return await p.create_plugin_ui(node_id)

    async def handle_delete_plugin_ui(self, session_id, player_id, node_id):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        return await p.delete_plugin_ui(node_id)

    async def handle_update_player_state(self, session_id, player_id, state):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        await p.update_state(state)

    async def handle_player_send_message(self, session_id, player_id, msg):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        p.send_message(msg)

    async def handle_restart_player_pipeline(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.get_player(player_id)
        p.restart_pipeline()

    async def handle_dump(self, session_id):
        assert self.project is not None
        session = self.get_session(session_id)
        logger.info("%s", pprint.pformat(self.project.serialize()))

    async def handle_render(self, session_id, callback_address, render_settings):
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

    async def handle_set_session_values(self, session_id, data):
        assert self.project is not None
        session = self.get_session(session_id)
        session.set_values(data, from_client=True)


class ProjectSubprocess(core.SubprocessMixin, ProjectProcess):
    pass
