#!/usr/bin/python3

import functools
import asyncio
import logging
import threading
import time
import uuid

from noisicaa import core
from noisicaa.core import ipc

from . import project
from . import mutations

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.id = uuid.uuid4().hex
        self.pending_mutations = []

    def cleanup(self):
        pass

    def publish_mutation(self, mutation):
        if not self.callback_stub.connected:
            self.pending_mutations.append(mutation)
            return

        logger.info("Publish mutation %s", mutation)

        callback_task = self.event_loop.create_task(
            self.callback_stub.call('PROJECT_MUTATION', mutation))
        callback_task.add_done_callback(
            functools.partial(
                self.publish_mutation_done, mutation=mutation))

    def publish_mutation_done(self, callback_task, mutation):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error(
                "PROJECT_MUTATION %s failed with exception:\n%s",
                mutation, exc)

    def callback_stub_connected(self):
        assert self.callback_stub.connected
        while self.pending_mutations:
            self.publish_mutation(self.pending_mutations.pop(0))

        self.event_loop.create_task(
            self.callback_stub.call('SESSION_READY'))


class ProjectProcessMixin(object):
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

    async def run(self):
        await self._shutting_down.wait()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def publish_mutation(self, mutation):
        for session in self.sessions.values():
            session.publish_mutation(mutation)

    def handle_start_session(self, client_address):
        client_stub = ipc.Stub(self.event_loop, client_address)
        connect_task = self.event_loop.create_task(client_stub.connect())
        session = Session(self.event_loop, client_stub)
        self.sessions[session.id] = session
        connect_task.add_done_callback(
            functools.partial(self._client_connected, session))
        return session.id

    def _client_connected(self, session, connect_task):
        assert connect_task.done()
        exc = connect_task.exception()
        if exc is not None:
            logger.error("Failed to connect to callback client: %s", exc)
            return

        session.callback_stub_connected()

    def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        session.cleanup()
        del self.sessions[session_id]

    def handle_shutdown(self):
        self._shutting_down.set()

    def _add_child_objects(self, obj):
        for prop in obj.list_properties():
            if prop.name == 'id':
                continue

            if isinstance(prop, core.ObjectProperty):
                child = getattr(obj, prop.name)
                if child is not None:
                    self._add_child_objects(child)
                    self.publish_mutation(mutations.AddObject(child))

            elif isinstance(prop, core.ObjectListProperty):
                for child in getattr(obj, prop.name):
                    assert child is not None
                    self._add_child_objects(child)
                    self.publish_mutation(mutations.AddObject(child))

    def _send_initial_mutations(self):
        self._add_child_objects(self.project)
        self.publish_mutation(mutations.AddObject(self.project))

    def handle_create(self, path):
        assert self.project is None
        self.project = project.Project()
        self.project.create(path)
        self._send_initial_mutations()
        for session in self.sessions.values():
            self.event_loop.create_task(
                session.callback_stub.call('PROJECT_READY'))
        return self.project.id

    def handle_create_inmemory(self):
        assert self.project is None
        self.project = project.BaseProject()
        self._send_initial_mutations()
        for session in self.sessions.values():
            self.event_loop.create_task(
                session.callback_stub.call('PROJECT_READY'))
        return self.project.id

    def handle_open(self, path):
        assert self.project is None
        self.project = project.Project()
        self.project.open(path)
        self._send_initial_mutations()
        for session in self.sessions.values():
            self.event_loop.create_task(
                session.callback_stub.call('PROJECT_READY'))
        return self.project.id

    def handle_close(self):
        assert self.project is not None
        self.project.close()
        self.project = None

    def handle_command(self, target, command, kwargs):
        assert self.project is not None
        cmd_cls = core.Command.get_subclass(command)
        cmd = cmd_cls(**kwargs)
        return self.project.dispatch_command(target, cmd)


class ProjectProcess(ProjectProcessMixin, core.ProcessImpl):
    pass
