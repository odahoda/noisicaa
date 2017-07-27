#!/usr/bin/python3

import asyncio
import functools
import logging
import sys
import uuid

import posix_ipc

from noisicaa import core
from noisicaa.core import ipc

from . import backend
from . import vm
from . import mutations
from . import node_db
from . import nodes

logger = logging.getLogger(__name__)


class InvalidSessionError(Exception): pass


class Session(object):
    def __init__(self, event_loop, callback_stub, flags):
        self.event_loop = event_loop
        self.callback_stub = callback_stub
        self.flags = flags or set()
        self.id = uuid.uuid4().hex
        self.pending_mutations = []

    async def cleanup(self):
        if self.callback_stub is not None:
            await self.callback_stub.close()
            self.callback_stub = None

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
        status = dict(status)

        if 'perf_data' not in self.flags and 'perf_data' in status:
            del status['perf_data']

        if status:
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
    def __init__(self, *args, shm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shm_name = shm
        self.shm = None
        self.__vm = None

    async def setup(self):
        await super().setup()

        self.__shutting_down = asyncio.Event()
        self.__shutdown_complete = asyncio.Event()

        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.server.add_command_handler(
            'SET_BACKEND', self.handle_set_backend)
        self.server.add_command_handler(
            'SET_BACKEND_PARAMETERS', self.handle_set_backend_parameters)
        self.server.add_command_handler(
            'PLAY_FILE', self.handle_play_file)
        self.server.add_command_handler(
            'ADD_EVENT', self.handle_add_event)
        self.server.add_command_handler(
            'PIPELINE_MUTATION', self.handle_pipeline_mutation)
        self.server.add_command_handler(
            'DUMP', self.handle_dump)

        self.node_db = node_db.NodeDB()
        self.node_db.add(nodes.WavFileSource)
        self.node_db.add(nodes.FluidSynthSource)
        self.node_db.add(nodes.IPCNode)
        self.node_db.add(nodes.PassThru)
        self.node_db.add(nodes.TrackControlSource)
        self.node_db.add(nodes.TrackAudioSource)
        self.node_db.add(nodes.TrackEventSource)
        self.node_db.add(nodes.CSoundFilter)
        self.node_db.add(nodes.CustomCSound)
        self.node_db.add(nodes.SamplePlayer)
        self.node_db.add(nodes.SplitChannels)
        self.node_db.add(nodes.JoinChannels)
        self.node_db.add(nodes.Ladspa)
        self.node_db.add(nodes.LV2)
        self.node_db.add(nodes.PipelineCrasher)

        if self.shm_name is not None:
            self.shm = posix_ipc.SharedMemory(self.shm_name)

        self.__vm = vm.PipelineVM(shm=self.shm)
        self.__vm.listeners.add('perf_data', self.perf_data_callback)
        self.__vm.listeners.add('node_state', self.node_state_callback)

        self.__vm.setup()

        sink = nodes.Sink()
        self.__vm.setup_node(sink)
        self.__vm.add_node(sink)

        self.sessions = {}

    async def cleanup(self):
        for session in self.sessions.values():
            session.cleanup()
        self.sessions.clear()

        if self.shm is not None:
            self.shm.close_fd()
            self.shm = None

        if self.__vm is not None:
            self.__vm.cleanup()
            self.__vm = None

        await super().cleanup()

    async def run(self):
        await self.__shutting_down.wait()
        logger.info("Shutting down...")
        self.__vm.cleanup()
        logger.info("Pipeline finished.")
        self.__shutdown_complete.set()

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

    def handle_start_session(self, client_address, flags):
        client_stub = ipc.Stub(self.event_loop, client_address)
        connect_task = self.event_loop.create_task(client_stub.connect())
        session = Session(self.event_loop, client_stub, flags)
        connect_task.add_done_callback(
            functools.partial(self.__client_connected, session))
        self.sessions[session.id] = session

        # Send initial mutations to build up the current pipeline
        # state.
        # TODO: reanimate
        # with self.__vm.reader_lock():
        #     for node in self.__vm.nodes:
        #         mutation = mutations.AddNode(node)
        #         session.publish_mutation(mutation)
        #     for node in self.__vm.nodes:
        #         for port in node.inputs.values():
        #             for upstream_port in port.inputs:
        #                 mutation = mutations.ConnectPorts(
        #                     upstream_port, port)
        #                 session.publish_mutation(mutation)

        return session.id

    def __client_connected(self, session, connect_task):
        assert connect_task.done()
        exc = connect_task.exception()
        if exc is not None:
            logger.error("Failed to connect to callback client: %s", exc)
            return

        session.callback_stub_connected()

    async def handle_end_session(self, session_id):
        session = self.get_session(session_id)
        await session.cleanup()
        del self.sessions[session_id]

    async def handle_shutdown(self):
        logger.info("Shutdown received.")
        self.__shutting_down.set()
        logger.info("Waiting for shutdown to complete...")
        await self.__shutdown_complete.wait()
        logger.info("Shutdown complete.")

    async def handle_pipeline_mutation(self, session_id, mutation):
        self.get_session(session_id)

        if isinstance(mutation, mutations.AddNode):
            node = self.node_db.create(mutation.node_type, **mutation.args)
            # TODO: schedule setup in a worker thread.
            self.__vm.setup_node(node)
            with self.__vm.writer_lock():
                self.__vm.add_node(node)
                self.__vm.update_spec()

        elif isinstance(mutation, mutations.RemoveNode):
            node = self.__vm.find_node(mutation.node_id)
            with self.__vm.writer_lock():
                self.__vm.remove_node(node)
                self.__vm.update_spec()
            node.cleanup()

        elif isinstance(mutation, mutations.ConnectPorts):
            node1 = self.__vm.find_node(mutation.src_node)
            try:
                port1 = node1.outputs[mutation.src_port]
            except KeyError as exc:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node1.id, type(node1).__name__, mutation.src_port)
                ).with_traceback(sys.exc_info()[2]) from None

            node2 = self.__vm.find_node(mutation.dest_node)
            try:
                port2 = node2.inputs[mutation.dest_port]
            except KeyError as exc:
                raise KeyError(
                    "Node %s (%s) has no port %s"
                    % (node2.id, type(node2).__name__, mutation.dest_port)
                ).with_traceback(sys.exc_info()[2]) from None
            with self.__vm.writer_lock():
                port2.connect(port1)
                self.__vm.update_spec()

        elif isinstance(mutation, mutations.DisconnectPorts):
            node1 = self.__vm.find_node(mutation.src_node)
            node2 = self.__vm.find_node(mutation.dest_node)
            with self.__vm.writer_lock():
                node2.inputs[mutation.dest_port].disconnect(node1.outputs[mutation.src_port])
                self.__vm.update_spec()

        elif isinstance(mutation, mutations.SetPortProperty):
            node = self.__vm.find_node(mutation.node)
            port = node.outputs[mutation.port]
            with self.__vm.writer_lock():
                port.set_prop(**mutation.kwargs)

        elif isinstance(mutation, mutations.SetNodeParameter):
            node = self.__vm.find_node(mutation.node)
            with self.__vm.writer_lock():
                node.set_param(**mutation.kwargs)

        else:
            raise ValueError(type(mutation))

    def handle_set_backend(self, session_id, name, parameters):
        self.get_session(session_id)

        result = None

        if name == 'pyaudio':
            be = backend.PyAudioBackend(parameters)
        elif name == 'null':
            be = backend.NullBackend(parameters)
        elif name == 'ipc':
            be = backend.IPCBackend(parameters)
            result = be.address
        elif name is None:
            be = None
        else:
            raise ValueError("Invalid backend name %s" % name)

        self.__vm.set_backend(be)
        return result

    def handle_set_backend_parameters(self, session_id, parameters):
        self.get_session(session_id)
        self.__vm.set_backend_parameters(parameters)

    def perf_data_callback(self, perf_data):
        self.event_loop.call_soon_threadsafe(
            functools.partial(
                self.publish_status, perf_data=perf_data))

    def node_state_callback(self, node_id, **kwargs):
        self.event_loop.call_soon_threadsafe(
            functools.partial(
                self.publish_status, node_state=(node_id, kwargs)))

    async def handle_play_file(self, session_id, path):
        self.get_session(session_id)

        node = nodes.WavFileSource(
            self.event_loop,
            path=path, loop=False, end_notification='end')
        await self.__vm.setup_node(node)

        self.__vm.notification_listener.add(
            node.id,
            functools.partial(self.play_file_done, node_id=node.id))

        with self.__vm.writer_lock():
            sink = self.__vm.find_node('sink')
            self.__vm.add_node(node)
            sink.inputs['in:left'].connect(node.outputs['out:left'])
            sink.inputs['in:right'].connect(node.outputs['out:right'])
            self.__vm.update_spec()

        return node.id

    def play_file_done(self, notification, node_id):
        with self.__vm.writer_lock():
            node = self.__vm.find_node(node_id)
            sink = self.__vm.find_node('sink')
            sink.inputs['in:left'].disconnect(node.outputs['out:left'])
            sink.inputs['in:right'].disconnect(node.outputs['out:right'])
            self.__vm.remove_node(node)
            self.__vm.update_spec()
        self.event_loop.create_task(node.cleanup())

    async def handle_add_event(self, session_id, entity_id, event):
        self.get_session(session_id)

        with self.__vm.writer_lock():
            backend = self.__vm.backend
            if backend is None:
                logger.warning(
                    "Ignoring event %s: no backend active:", event)

            backend.add_event(entity_id, event)

    def handle_dump(self, session_id):
        self.__vm.dump()


class AudioProcProcess(AudioProcProcessMixin, core.ProcessImpl):
    pass
