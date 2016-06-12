#!/usr/bin/python3

import asyncio
import logging
import threading
import time
import uuid

from noisicaa import core
from noisicaa.core import ipc

from . import project

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, callback_stub):
        self.id = uuid.uuid4().hex
        self.callback_stub = callback_stub
        self.listeners = {}

    def cleanup(self):
        for listener in self.listeners.values():
            listener.remove()
        self.listeners.clear()


class ListenerProxy(object):
    def __init__(self, event_loop, session):
        self.event_loop = event_loop
        self.session = session
        self.listener = None

    @property
    def id(self):
        return self.listener.id

    def remove(self):
        self.listener.remove()
        self.listener = None

    def __call__(self, *args):
        callback_task = self.event_loop.create_task(
            self.session.callback_stub.call(
                'LISTENER_CALLBACK', self.session.id, self.listener.id, args))
        callback_task.add_done_callback(self.callback_done)

    def callback_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("LISTENER_CALLBACK failed with exception: %s", exc)


class ProjectProcess(core.ProcessImpl):
    async def setup(self):
        self._shutting_down = asyncio.Event()
        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('GETPROPS', self.handle_getprops)
        self.server.add_command_handler(
            'ADD_LISTENER', self.handle_add_listener)
        self.server.add_command_handler(
            'REMOVE_LISTENER', self.handle_remove_listener)
        self.server.add_command_handler('TEST', self.handle_test)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.project = project.Project()
        self.sessions = {}

    async def run(self):
        await self._shutting_down.wait()

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def handle_start_session(self, client_address):
        client_stub = ipc.Stub(self.event_loop, client_address)
        self.event_loop.create_task(client_stub.connect())
        session = Session(client_stub)
        self.sessions[session.id] = session
        return session.id

    def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        session.cleanup()
        del self.sessions[session_id]

    def handle_getprops(self, session_id, address, properties):
        session = self.get_session(session_id)

        obj = self.project.get_object(address)

        response = {}
        for prop in properties:
            value = getattr(obj, prop)
            if isinstance(value, core.StateBase):
                response[prop] = ['proxy', value.address]
            else:
                response[prop] = ['value', value]

        return response

    def handle_add_listener(self, session_id, address, prop):
        session = self.get_session(session_id)

        obj = self.project.get_object(address)
        proxy = ListenerProxy(self.event_loop, session)
        proxy.listener = obj.listeners.add(prop, proxy)
        session.listeners[proxy.id] = proxy
        return proxy.id

    def handle_remove_listener(self, session_id, listener_id):
        session = self.get_session(session_id)
        listener = session.listeners[listener_id]
        listener.remove()
        del session.listeners[listener_id]

    def handle_shutdown(self):
        self._shutting_down.set()

    def handle_test(self):
        self.project.current_sheet = (self.project.current_sheet or 0) + 1
