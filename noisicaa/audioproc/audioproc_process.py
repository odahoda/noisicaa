#!/usr/bin/python3

import asyncio
import functools
import logging
import uuid

from noisicaa import core
from noisicaa.core import ipc

from . import backend
from . import pipeline
from . import mutations
from . import node_db
from .filter import scale
from .source import whitenoise
from .source import silence
from .source import wavfile
from .source import fluidsynth

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

        callback_task = self.event_loop.create_task(
            self.callback_stub.call('PIPELINE_MUTATION', mutation))
        callback_task.add_done_callback(self.publish_mutation_done)

    def publish_mutation_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error(
                "PUBLISH_MUTATION failed with exception: %s", exc)

    def publish_status(self, status):
        callback_task = self.event_loop.create_task(
            self.callback_stub.call('PIPELINE_STATUS', status))
        callback_task.add_done_callback(self.publish_status_done)

    def publish_status_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("PUBLISH_STATUS failed with exception: %s", exc)

    def callback_stub_connected(self):
        assert self.callback_stub.connected
        while self.pending_mutations:
            self.publish_mutation(self.pending_mutations.pop(0))


class AudioProcProcessMixin(object):
    async def setup(self):
        await super().setup()

        self._shutting_down = asyncio.Event()

        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.server.add_command_handler(
            'LIST_NODE_TYPES', self.handle_list_node_types)
        self.server.add_command_handler(
            'ADD_NODE', self.handle_add_node)
        self.server.add_command_handler(
            'REMOVE_NODE', self.handle_remove_node)
        self.server.add_command_handler(
            'CONNECT_PORTS', self.handle_connect_ports)
        self.server.add_command_handler(
            'DISCONNECT_PORTS', self.handle_disconnect_ports)

        self.node_db = node_db.NodeDB()
        self.node_db.add(scale.Scale)
        self.node_db.add(silence.SilenceSource)
        self.node_db.add(whitenoise.WhiteNoiseSource)
        self.node_db.add(wavfile.WavFileSource)
        self.node_db.add(fluidsynth.FluidSynthSource)

        self.pipeline = pipeline.Pipeline()
        self.pipeline.utilization_callback = self.utilization_callback

        self.backend = backend.PyAudioBackend()
        self.pipeline.set_backend(self.backend)

        self.audiosink = backend.AudioSinkNode()
        self.audiosink.setup()
        self.pipeline.add_node(self.audiosink)

        self.midisource = backend.MidiSourceNode()
        self.midisource.setup()
        self.pipeline.add_node(self.midisource)

        self.pipeline.start()

        self.sessions = {}

    async def cleanup(self):
        self.pipeline.stop()
        await super().cleanup()

    async def run(self):
        await self._shutting_down.wait()

    def utilization_callback(self, utilization):
        self.event_loop.call_soon_threadsafe(
            functools.partial(
                self.publish_status, utilization=utilization))

    def get_session(self, session_id):
        try:
            return self.sessions[session_id]
        except KeyError:
            raise InvalidSessionError

    def publish_mutation(self, mutation):
        for session in self.sessions.values():
            session.publish_mutation(mutation)

    def publish_status(self, **kwargs):
        for session in self.sessions.values():
            session.publish_status(kwargs)

    def handle_start_session(self, client_address):
        client_stub = ipc.Stub(self.event_loop, client_address)
        connect_task = self.event_loop.create_task(client_stub.connect())
        session = Session(self.event_loop, client_stub)
        connect_task.add_done_callback(
            functools.partial(self._client_connected, session))
        self.sessions[session.id] = session

        # Send initial mutations to build up the current pipeline
        # state.
        with self.pipeline.reader_lock():
            for node in self.pipeline._nodes:
                mutation = mutations.AddNode(node)
                session.publish_mutation(mutation)
            for node in self.pipeline._nodes:
                for port in node.inputs.values():
                    for upstream_port in port.inputs:
                        mutation = mutations.ConnectPorts(
                            port, upstream_port)
                        session.publish_mutation(mutation)

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

    def handle_list_node_types(self, session_id):
        self.get_session(session_id)
        return self.node_db.node_types

    def handle_add_node(self, session_id, name, args):
        session = self.get_session(session_id)
        node = self.node_db.create(name, args)
        node.setup()
        with self.pipeline.writer_lock():
            self.pipeline.add_node(node)
        self.publish_mutation(mutations.AddNode(node))
        return node.id

    def handle_remove_node(self, session_id, node_id):
        session = self.get_session(session_id)
        node = self.pipeline.find_node(node_id)
        with self.pipeline.writer_lock():
            self.pipeline.remove_node(node)
        node.cleanup()
        self.publish_mutation(mutations.RemoveNode(node))

    def handle_connect_ports(
            self, session_id, node1_id, port1_name, node2_id, port2_name):
        session = self.get_session(session_id)
        node1 = self.pipeline.find_node(node1_id)
        node2 = self.pipeline.find_node(node2_id)
        with self.pipeline.writer_lock():
            node2.inputs[port2_name].connect(node1.outputs[port1_name])
        self.publish_mutation(
            mutations.ConnectPorts(
                node1.outputs[port1_name], node2.inputs[port2_name]))

    def handle_disconnect_ports(
            self, session_id, node1_id, port1_name, node2_id, port2_name):
        session = self.get_session(session_id)
        node1 = self.pipeline.find_node(node1_id)
        node2 = self.pipeline.find_node(node2_id)
        with self.pipeline.writer_lock():
            node2.inputs[port2_name].disconnect(node1.outputs[port1_name])
        self.publish_mutation(
            mutations.DisconnectPorts(
                node1.outputs[port1_name], node2.inputs[port2_name]))


class AudioProcProcess(AudioProcProcessMixin, core.ProcessImpl):
    pass
