#!/usr/bin/python3

import functools
import asyncio
import logging
import threading
import time
import uuid

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc

from . import project
from . import mutations
from . import commands

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.id = uuid.uuid4().hex

    def cleanup(self):
        pass

    async def publish_mutation(self, mutation):
        assert self.callback_stub.connected
        logger.info("Publish mutation %s", mutation)

        try:
            await self.callback_stub.call('PROJECT_MUTATION', mutation)
        except Exception:
            logger.exception(
                "PROJECT_MUTATION %s failed with exception", mutation)


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


class ProjectProcessMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.audioproc_client = None

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
        self.project = None
        self.sessions = {}
        self.pending_mutations = []

        self.audioproc_address = await self.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'project-%s' % id(self))
        self.audioproc_client = AudioProcClient(
            self.event_loop, self.server)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(self.audioproc_address)

        nid = await self.audioproc_client.add_node('wavfile', path='/usr/share/sounds/purple/logout.wav', loop=True)
        await self.audioproc_client.connect_ports(nid, 'out', 'sink', 'in')

        self.audiostream_address = await self.audioproc_client.set_backend('ipc')

    async def cleanup(self):
        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None
            self.audioproc_address = None
            self.audiostream_address = None

    async def run(self):
        await self._shutting_down.wait()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def handle_project_mutation(self, mutation):
        logger.info("mutation: %s", mutation)
        mtype, obj = mutation[:2]
        if mtype == 'update_objlist':
            prop_name, cmd = mutation[2:4]
            if cmd == 'insert':
                idx, child = mutation[4:]
                for mutation in self.add_object_mutations(child):
                    self.pending_mutations.append(mutation)
                self.pending_mutations.append(mutations.UpdateObjectList(obj, prop_name, 'insert', idx, child.id))
            elif cmd == 'delete':
                idx = mutation[4]
                self.pending_mutations.append(mutations.UpdateObjectList(obj, prop_name, 'delete', idx))
            elif cmd == 'clear':
                self.pending_mutations.append(mutations.UpdateObjectList(obj, prop_name, 'clear'))
            else:
                raise ValueError(cmd)

        elif mtype == 'update_list':
            prop_name, cmd = mutation[2:4]
            if cmd == 'insert':
                idx, value = mutation[4:]
                self.pending_mutations.append(mutations.UpdateList(obj, prop_name, 'insert', idx, value))
            elif cmd == 'delete':
                idx = mutation[4]
                self.pending_mutations.append(mutations.UpdateList(obj, prop_name, 'delete', idx))
            elif cmd == 'clear':
                self.pending_mutations.append(mutations.UpdateList(obj, prop_name, 'clear'))
            else:
                raise ValueError(cmd)

        elif mtype == 'update_property':
            prop_name, old_value, new_value = mutation[2:]
            self.pending_mutations.append(mutations.SetProperties(obj, [prop_name]))

        else:
            raise ValueError(mtype)

    async def publish_mutation(self, mutation):
        tasks = []
        for session in self.sessions.values():
            tasks.append(self.event_loop.create_task(
                session.publish_mutation(mutation)))
        await asyncio.wait(tasks, loop=self.event_loop)

    async def handle_start_session(self, client_address):
        client_stub = ipc.Stub(self.event_loop, client_address)
        await client_stub.connect()
        session = Session(self.event_loop, client_stub)
        self.sessions[session.id] = session
        if self.project is not None:
            for mutation in self.add_object_mutations(self.project):
                await session.publish_mutation(mutation)
            return session.id, self.audiostream_address, self.project.id
        return session.id, self.audiostream_address, None

    def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        session.cleanup()
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
        for mutation in self.add_object_mutations(self.project):
            await self.publish_mutation(mutation)

    async def handle_create(self, path):
        assert self.project is None
        self.project = project.Project()
        self.project.create(path)
        await self.send_initial_mutations()
        self.project.set_mutation_callback(self.handle_project_mutation)
        return self.project.id

    async def handle_create_inmemory(self):
        assert self.project is None
        self.project = project.BaseProject()
        await self.send_initial_mutations()
        self.project.set_mutation_callback(self.handle_project_mutation)
        return self.project.id

    async def handle_open(self, path):
        assert self.project is None
        self.project = project.Project()
        self.project.open(path)
        await self.send_initial_mutations()
        self.project.set_mutation_callback(self.handle_project_mutation)
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

        for mutation in mutations:
            await self.publish_mutation(mutation)
        return result


class ProjectProcess(ProjectProcessMixin, core.ProcessImpl):
    pass
