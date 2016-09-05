#!/usr/bin/python3

import asyncio
import functools
import logging
import pprint
import threading
import time
import traceback
import uuid

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import node_db

from . import project
from . import sheet
from . import mutations
from . import commands
from . import player
from . import state
from . import score_track

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.id = uuid.uuid4().hex
        self.players = {}

    async def cleanup(self):
        for p in self.players.values():
            await p.cleanup()
        self.players.clear()

    async def publish_mutations(self, mutations):
        assert self.callback_stub.connected

        logger.info(
            "Publish mutations:\n%s",
            '\n'.join(str(mutation) for mutation in mutations))

        try:
            await self.callback_stub.call('PROJECT_MUTATIONS', mutations)
        except Exception:
            logger.error(
                "PROJECT_MUTATIONS %s failed with exception:\n%s",
                mutations, traceback.format_exc())


class AudioProcClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class AudioProcClient(
        audioproc.AudioProcClientMixin, AudioProcClientImpl):
    pass


class NodeDBClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class NodeDBClient(node_db.NodeDBClientMixin, NodeDBClientImpl):
    pass


class ProjectProcessMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._shutting_down = None

        self.node_db = None
        self.project = None
        self.sessions = {}
        self.pending_mutations = []

    async def setup(self):
        await super().setup()

        self._shutting_down = asyncio.Event()

        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.server.add_command_handler('CREATE', self.handle_create)
        self.server.add_command_handler(
            'CREATE_INMEMORY', self.handle_create_inmemory)
        self.server.add_command_handler('OPEN', self.handle_open)
        self.server.add_command_handler('CLOSE', self.handle_close)
        self.server.add_command_handler('COMMAND', self.handle_command)
        self.server.add_command_handler('UNDO', self.handle_undo)
        self.server.add_command_handler('REDO', self.handle_redo)
        self.server.add_command_handler('SERIALIZE', self.handle_serialize)
        self.server.add_command_handler(
            'CREATE_PLAYER', self.handle_create_player)
        self.server.add_command_handler(
            'DELETE_PLAYER', self.handle_delete_player)
        self.server.add_command_handler(
            'GET_PLAYER_AUDIOPROC_ADDRESS',
            self.handle_get_player_audioproc_address)
        self.server.add_command_handler(
            'PLAYER_START', self.handle_player_start)
        self.server.add_command_handler(
            'PLAYER_PAUSE', self.handle_player_pause)
        self.server.add_command_handler(
            'PLAYER_STOP', self.handle_player_stop)
        self.server.add_command_handler(
            'DUMP', self.handle_dump)

        node_db_address = await self.manager.call(
            'CREATE_NODE_DB_PROCESS')
        self.node_db = NodeDBClient(self.event_loop, self.server)
        await self.node_db.setup()
        await self.node_db.connect(node_db_address)

    async def cleanup(self):
        if self.node_db is None:
            self.node_db.close()
            self.node_db.cleanup()
            self.node_db = None
        await super().cleanup()

    async def run(self):
        await self._shutting_down.wait()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

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
        for session in self.sessions.values():
            tasks.append(self.event_loop.create_task(
                session.publish_mutations(mutations)))
        await asyncio.wait(tasks, loop=self.event_loop)

    async def handle_start_session(self, client_address):
        client_stub = ipc.Stub(self.event_loop, client_address)
        await client_stub.connect()
        session = Session(self.event_loop, client_stub)
        self.sessions[session.id] = session
        if self.project is not None:
            await session.publish_mutations(
                list(self.add_object_mutations(self.project)))
            return session.id, self.project.id
        return session.id, None

    async def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        await session.cleanup()
        del self.sessions[session_id]

    def handle_shutdown(self):
        self._shutting_down.set()

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

    def _create_blank_project(self, project_cls):
        project = project_cls(node_db=self.node_db)
        s = sheet.Sheet(name='Sheet 1', num_tracks=0)
        project.add_sheet(s)
        t = score_track.ScoreTrack(name="Track 1")
        s.add_track(s.master_group, 0, t)
        return project

    async def handle_create(self, path):
        assert self.project is None
        self.project = self._create_blank_project(project.Project)
        self.project.create(path)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        return self.project.id

    async def handle_create_inmemory(self):
        assert self.project is None
        self.project = self._create_blank_project(project.BaseProject)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        return self.project.id

    async def handle_open(self, path):
        assert self.project is None
        self.project = project.Project(node_db=self.node_db)
        self.project.open(path)
        await self.send_initial_mutations()
        self.project.listeners.add(
            'model_changes', self.handle_model_change)
        return self.project.id

    def handle_close(self):
        assert self.project is not None

        tasks = []
        for session in self.sessions.values():
            tasks.append(self.event_loop.create_task(
                session.callback_stub.call('PROJECT_CLOSED')))
        asyncio.wait(tasks, loop=self.event_loop)

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
        return obj.serialize()

    async def handle_create_player(
        self, session_id, client_address, sheet_id):
        session = self.get_session(session_id)
        assert self.project is not None

        sheet = self.project.get_object(sheet_id)

        p = player.Player(
            sheet, client_address, self.manager, self.event_loop)
        await p.setup()

        session.players[p.id] = p

        return p.id, p.proxy_address

    async def handle_get_player_audioproc_address(
        self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.players[player_id]
        return p.audioproc_address

    async def handle_delete_player(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.players[player_id]
        await p.cleanup()
        del session.players[player_id]

    async def handle_player_start(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.players[player_id]
        await p.playback_start()

    async def handle_player_pause(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.players[player_id]
        await p.playback_pause()

    async def handle_player_stop(self, session_id, player_id):
        session = self.get_session(session_id)
        p = session.players[player_id]
        await p.playback_stop()

    async def handle_dump(self, session_id):
        assert self.project is not None
        session = self.get_session(session_id)
        logger.info("%s", pprint.pformat(self.project.serialize()))


class ProjectProcess(ProjectProcessMixin, core.ProcessImpl):
    pass
