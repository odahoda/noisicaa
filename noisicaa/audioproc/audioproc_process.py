#!/usr/bin/python3

import asyncio
import logging
import uuid

from noisicaa import core
from noisicaa.core import ipc

from . import pipeline
from .sink import pyaudio
from .source import whitenoise

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, callback_stub):
        self.id = uuid.uuid4().hex
        self.callback_stub = callback_stub

    def cleanup(self):
        pass


class AudioProcProcessMixin(object):
    async def setup(self):
        await super().setup()
        self._shutting_down = asyncio.Event()
        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.pipeline = pipeline.Pipeline()

        noise = whitenoise.WhiteNoiseSource()
        self.pipeline.add_node(noise)
        sink = pyaudio.PyAudioSink()
        self.pipeline.set_sink(sink)
        sink.inputs['in'].connect(noise.outputs['out'])
        self.pipeline.start()

        self.sessions = {}

    async def cleanup(self):
        self.pipeline.stop()
        await super().cleanup()

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

    def handle_shutdown(self):
        self._shutting_down.set()


class AudioProcProcess(AudioProcProcessMixin, core.ProcessImpl):
    pass
