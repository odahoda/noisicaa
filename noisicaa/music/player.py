#!/usr/bin/python3

import asyncio
import enum
import functools
import itertools
import logging
import os
import os.path
import queue
import random
import sys
import tempfile
import threading
import time
import uuid

import posix_ipc

from noisicaa import core
from noisicaa.core import ipc
from noisicaa.core import model_base
from noisicaa import audioproc
from noisicaa import music

from . import project
from . import mutations
from . import commands
from . import model
from . import time_mapper
from . import project_client

logger = logging.getLogger(__name__)


class BackendState(enum.Enum):
    Stopped = 'stopped'
    Starting = 'starting'
    Running = 'running'
    Crashed = 'crashed'
    Stopping = 'stopping'


class BackendManager(object):
    def __init__(self, event_loop):
        self._event_loop = event_loop
        self._state = BackendState.Stopped
        self._state_changed = asyncio.Event(loop=self._event_loop)
        self._listeners = core.CallbackRegistry()

    @property
    def is_running(self):
        return self._state == BackendState.Running

    def add_state_listener(self, callback):
        return self._listeners.add('state-changed', callback)

    async def wait_until_running(self):
        while True:
            if self._state == BackendState.Running:
                return
            if self._state == BackendState.Stopped:
                raise RuntimeError

            await self._state_changed.wait()
            self._state_changed.clear()

    async def wait_until_stopped(self):
        while True:
            if self._state == BackendState.Stopped:
                return

            await self._state_changed.wait()
            self._state_changed.clear()

    def start(self):
        if self._state in (BackendState.Running, BackendState.Starting):
            pass

        elif self._state == BackendState.Stopped:
            self._set_state(BackendState.Starting)
            task = self._event_loop.create_task(self.start_backend())
            task.add_done_callback(self._start_backend_finished)

        else:
            raise AssertionError("Unexpected state %s" % self._state.value)

    def stop(self):
        if self._state in (BackendState.Stopped, BackendState.Stopping):
            pass

        elif self._state == BackendState.Crashed:
            task = self._event_loop.create_task(self.cleanup())
            task.add_done_callback(self._cleanup_finished)

        elif self._state == BackendState.Running:
            task = self._event_loop.create_task(self.stop_backend())
            task.add_done_callback(self._stop_backend_finished)

        else:
            raise AssertionError("Unexpected state %s" % self._state.value)

    def backend_crashed(self):
        if self._state in (BackendState.Crashed, BackendState.Stopping, BackendState.Stopped):
            pass

        elif self._state == BackendState.Running:
            self._set_state(BackendState.Crashed)
            task = self._event_loop.create_task(self.cleanup())
            task.add_done_callback(self._cleanup_finished)

        else:
            raise AssertionError("Unexpected state %s" % self._state.value)

    def _set_state(self, new_state):
        assert new_state != self._state
        logger.info("State %s -> %s", self._state.value, new_state.value)
        self._state = new_state
        self._state_changed.set()
        self._listeners.call('state-changed', new_state)

    def _start_backend_finished(self, task):
        exc = task.exception()
        if exc is not None:
            raise exc
            # self._set_state(BackendState.Crashed)
            # self._event_loop.create_task(self.cleanup())

        self._set_state(BackendState.Running)
        self._event_loop.create_task(self.backend_started())

    def _stop_backend_finished(self, task):
        exc = task.exception()
        if exc is not None:
            raise exc

        task = self._event_loop.create_task(self.cleanup())
        task.add_done_callback(self._cleanup_finished)

    def _cleanup_finished(self, task):
        exc = task.exception()
        if exc is not None:
            raise exc
        self._set_state(BackendState.Stopped)
        self._event_loop.create_task(self.backend_stopped())

    async def start_backend(self):
        raise NotImplementedError

    async def stop_backend(self):
        raise NotImplementedError

    async def cleanup(self):
        raise NotImplementedError

    async def backend_started(self):
        pass

    async def backend_stopped(self):
        pass


class AudioProcBackend(BackendManager):
    def __init__(self, player, event_loop):
        super().__init__(event_loop)
        self._player = player

    async def start_backend(self):
        await self._player.start_audioproc()

    async def stop_backend(self):
        await self._player.stop_audioproc()

    async def cleanup(self):
        await self._player.stop_audioproc()

    async def backend_started(self):
        await self._player.audioproc_started()

    async def backend_stopped(self):
        await self._player.audioproc_stopped()


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


class AudioStreamProxy(object):
    def __init__(self, player, socket_dir=None):
        self._player = player

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'player.%s.pipe' % uuid.uuid4().hex)

        self._lock = threading.Lock()

        self._server = audioproc.AudioStreamServer(self.address)
        self._client = None

        self._stopped = threading.Event()
        self._settings_queue = queue.Queue()
        self._message_queue = queue.Queue()
        self._thread = threading.Thread(target=self.main)

    def setup(self):
        self._server.setup()
        self._thread.start()

    def cleanup(self):
        self._server.close()
        self._stopped.set()
        self._thread.join()
        self._server.cleanup()

    def set_client(self, client):
        if client is not None:
            logger.info("Proxy will talk to %s...", client.address)
        else:
            logger.info("Disabling proxy backend.")
        with self._lock:
            self._client = client

    def update_settings(self, settings):
        self._settings_queue.put(settings)

    def send_message(self, msg):
        self._message_queue.put(msg)

    def main(self):
        sample_pos_offset = None
        settings = project_client.PlayerSettings()
        settings.state = 'stopped'
        settings.sample_pos = 0
        tmap = time_mapper.TimeMapper(self._player.sheet)

        logger.info("Player proxy started.")
        try:
            while not self._stopped.is_set():
                try:
                    server_request = self._server.receive_frame()
                except audioproc.StreamClosed:
                    logger.warning("Stream to PlayerClient closed.")
                    raise

                perf = core.PerfStats()

                request = audioproc.FrameData.new_message()
                request.samplePos = server_request.samplePos
                request.frameSize = server_request.frameSize

                entities = {}
                messages = []

                while True:
                    try:
                        new_settings = self._settings_queue.get_nowait()
                    except queue.Empty:
                        break

                    if new_settings.sample_pos is not None:
                        settings.sample_pos = new_settings.sample_pos
                        if settings.state == 'playing':
                            sample_pos_offset = request.samplePos - settings.sample_pos
                        self._player.publish_status_async(
                            playback_pos=(
                                settings.sample_pos,
                                request.frameSize))

                    if new_settings.loop_start is not None:
                        settings.loop_start = new_settings.loop_start
                        self._player.publish_status_async(
                            loop_start=settings.loop_start)

                    if new_settings.loop_end is not None:
                        settings.loop_end = new_settings.loop_end
                        self._player.publish_status_async(
                            loop_end=settings.loop_end)

                    if new_settings.loop is not None:
                        settings.loop = new_settings.loop
                        self._player.publish_status_async(
                            loop=settings.loop)

                    if new_settings.state is not None:
                        new_state = new_settings.state
                        if settings.state != new_state:
                            if new_state == 'playing':
                                sample_pos_offset = request.samplePos - settings.sample_pos
                            settings.state = new_state
                            self._player.publish_status_async(
                                player_state=new_state)

                while True:
                    try:
                        msg = self._message_queue.get_nowait()
                    except queue.Empty:
                        break

                    logger.info(str(msg))
                    messages.append(msg)

                if settings.state == 'playing':
                    self._player.publish_status_async(
                        playback_pos=(
                            request.samplePos - sample_pos_offset,
                            request.frameSize))

                    if settings.loop_start is not None:
                        range_start = settings.loop_start
                    else:
                        range_start = 0

                    if settings.loop_end is not None:
                        range_end = settings.loop_end
                    else:
                        range_end = tmap.total_duration_samples

                    with perf.track('get_track_entities'):
                        duration = request.frameSize
                        out_sample_pos = request.samplePos
                        while duration > 0:
                            end_pos = min(settings.sample_pos + duration, range_end)
                            self._player.get_track_entities(
                                entities,
                                settings.sample_pos, end_pos,
                                sample_pos_offset)

                            duration -= end_pos - settings.sample_pos
                            out_sample_pos += end_pos - settings.sample_pos

                            if end_pos >= range_end:
                                settings.sample_pos = range_start
                                sample_pos_offset = out_sample_pos - settings.sample_pos
                                if not settings.loop:
                                    settings.state = 'stopped'
                                    self._player.publish_status_async(
                                        player_state=settings.state)
                                    break
                            else:
                                settings.sample_pos = end_pos

                request.init(
                    'entities',
                    len(server_request.entities) + len(entities))
                for idx, entity in enumerate(
                        itertools.chain(
                            server_request.entities, entities.values())):
                    request.entities[idx] = entity

                request.init(
                    'messages',
                    len(server_request.messages) + len(messages))
                for idx, msg in enumerate(
                        itertools.chain(
                            server_request.messages, messages)):
                    request.messages[idx] = msg

                with self._lock:
                    if self._client is not None:
                        try:
                            with perf.track('send_frame'):
                                self._client.send_frame(request)
                            with perf.track('receive_frame'):
                                client_response = self._client.receive_frame()
                            perf.add_spans(client_response.perfData)

                        except audioproc.StreamClosed:
                            logger.warning("Stream to pipeline closed.")
                            self._player.event_loop.call_soon_threadsafe(
                                self._player.audioproc_backend.backend_crashed)
                            self._client = None

                    if self._client is None:
                        client_response = audioproc.FrameData.new_message()
                        client_response.samplePos = request.samplePos
                        client_response.frameSize = request.frameSize


                response = audioproc.FrameData.new_message()
                response.samplePos = client_response.samplePos
                response.frameSize = client_response.frameSize
                response.init('entities', len(client_response.entities))
                for idx, entity in enumerate(client_response.entities):
                    response.entities[idx] = entity
                response.perfData = perf.serialize()

                try:
                    self._server.send_frame(response)
                except audioproc.StreamClosed:
                    logger.warning("Stream to PlayerClient closed.")
                    raise

        except audioproc.StreamClosed:
            pass

        except:  # pylint: disable=bare-except
            sys.excepthook(*sys.exc_info())

        finally:
            logger.info("Player proxy terminated.")


class Player(object):
    def __init__(self, sheet, callback_address, manager, event_loop):
        self.sheet = sheet
        self.manager = manager
        self.callback_address = callback_address
        self.event_loop = event_loop

        self.listeners = core.CallbackRegistry()

        self.id = uuid.uuid4().hex
        self.server = ipc.Server(self.event_loop, 'player')

        self.callback_stub = None

        self.audioproc_backend = None
        self.audioproc_backend_state_listener = None
        self.audioproc_backend_last_crash_time = None
        self.audioproc_address = None
        self.audioproc_client = None
        self.audioproc_status_listener = None
        self.audioproc_ready = None
        self.audiostream_address = None
        self.audiostream_client = None

        self.mutation_listener = None
        self.pending_pipeline_mutations = None

        self.proxy = None

        self.track_entity_sources = {}
        self.group_listeners = {}

    @property
    def proxy_address(self):
        assert self.proxy is not None
        return self.proxy.address

    async def setup(self):
        logger.info("Setting up player instance %s..", self.id)

        logger.info("Setting up player server...")
        await self.server.setup()
        logger.info("Player server address: %s", self.server.address)

        logger.info("Connecting to client callback server %s..", self.callback_address)
        self.callback_stub = ipc.Stub(
            self.event_loop, self.callback_address)
        await self.callback_stub.connect()

        logger.info("Starting audio stream proxy...")
        self.proxy = AudioStreamProxy(self)
        self.proxy.setup()

        self.mutation_listener = self.sheet.listeners.add(
            'pipeline_mutations', self.handle_pipeline_mutation)

        self.audioproc_shm = posix_ipc.SharedMemory(
            '/noisicaa-player.%s' % self.id,
            posix_ipc.O_CREAT | posix_ipc.O_EXCL,
            size=1024)

        logger.info("Starting audio process...")
        self.audioproc_ready = asyncio.Event(loop=self.event_loop)
        self.audioproc_backend = AudioProcBackend(self, self.event_loop)
        self.audioproc_backend_state_listener = self.audioproc_backend.add_state_listener(
            self.audioproc_state_changed)
        self.audioproc_backend.start()

        # TODO: with timeout
        await self.audioproc_ready.wait()

        self.add_track(self.sheet.master_group)

        logger.info("Player instance %s setup complete.", self.id)

    async def cleanup(self):
        logger.info("Cleaning up player instance %s..", self.id)

        for listener in self.group_listeners.values():
            listener.remove()
        self.group_listeners.clear()

        for entity_source in self.track_entity_sources.values():
            entity_source.close()
        self.track_entity_sources.clear()

        if self.mutation_listener is not None:
            self.mutation_listener.remove()
            self.mutation_listener = None

        if self.audioproc_backend_state_listener is not None:
            self.audioproc_backend_state_listener.remove()
            self.audioproc_backend_state_listener = None

        if self.audioproc_backend is not None:
            self.audioproc_backend = None

        self.audioproc_ready = None

        logger.info("Stopping audio process...")
        await self.stop_audioproc()

        if self.audioproc_shm is not None:
            self.audioproc_shm.close_fd()
            self.audioproc_shm.unlink()
            self.audioproc_shm = None

        if self.callback_stub is not None:
            logger.info("Closing connection to client callback server...")
            await self.callback_stub.close()
            self.callback_stub = None

        if self.proxy is not None:
            logger.info("Stopping audio stream proxy...")
            self.proxy.cleanup()
            self.proxy = None

        logger.info("Cleaning up player server...")
        await self.server.cleanup()

        logger.info("Player instance %s cleanup complete.", self.id)

    def audioproc_state_changed(self, state):
        self.publish_status_async(pipeline_state=state.value)

    async def start_audioproc(self):
        logger.info("Starting audioproc backend...")

        logger.info("Creating audioproc process...")
        self.audioproc_address = await self.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'player',
            shm=self.audioproc_shm.name)

        logger.info("Creating audioproc client...")
        self.audioproc_client = AudioProcClient(
            self.event_loop, self.server)
        self.audioproc_status_listener = self.audioproc_client.listeners.add(
            'pipeline_status', functools.partial(
                self.listeners.call, 'pipeline_status'))
        await self.audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await self.audioproc_client.connect(self.audioproc_address)

        logger.info("Setting backend...")
        self.audiostream_address = await self.audioproc_client.set_backend('ipc')

        logger.info("Creating audiostream client...")
        self.audiostream_client = audioproc.AudioStreamClient(self.audiostream_address)
        self.audiostream_client.setup()

        logger.info("Audioproc backend started.")

    async def audioproc_started(self):
        self.pending_pipeline_mutations = []
        self.sheet.add_to_pipeline()
        pipeline_mutations = self.pending_pipeline_mutations[:]
        self.pending_pipeline_mutations = None

        try:
            for mutation in pipeline_mutations:
                await self.publish_pipeline_mutation(mutation)

            await self.audioproc_client.dump()

            self.proxy.set_client(self.audiostream_client)

            self.audioproc_ready.set()

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    async def stop_audioproc(self):
        logger.info("Stopping audioproc backend...")

        if self.audiostream_client is not None:
            self.proxy.set_client(None)
            self.audiostream_client.cleanup()
            self.audiostream_client = None
            self.audiostream_address = None

        if self.audioproc_status_listener is not None:
            self.audioproc_status_listener.remove()
            self.audioproc_status_listener = None

        if self.audioproc_client is not None:
            logger.info("Disconnecting audioproc client...")
            try:
                await self.audioproc_client.disconnect(shutdown=True)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
            await self.audioproc_client.cleanup()
            self.audioproc_client = None
            self.audioproc_address = None
            self.audiostream_address = None

        logger.info("Audioproc backend stopped.")

    async def audioproc_stopped(self):
        if self.audioproc_shm is not None:
            os.lseek(self.audioproc_shm.fd, 0, os.SEEK_SET)
            logger.info(
                "audioproc_shm:\n%s\n%s",
                os.read(self.audioproc_shm.fd, 512).hex(),
                os.read(self.audioproc_shm.fd, 512).hex())

        now = time.time()
        if (self.audioproc_backend_last_crash_time is None
                or now - self.audioproc_backend_last_crash_time > 30):
            self.audioproc_backend.start()
        else:
            self.publish_status_async(pipeline_disabled=True)
        self.audioproc_backend_last_crash_time = now

    def restart_pipeline(self):
        self.audioproc_backend.start()

    def publish_status_async(self, **kwargs):
        callback_task = asyncio.run_coroutine_threadsafe(
            self.callback_stub.call('PLAYER_STATUS', self.id, kwargs),
            self.event_loop)
        callback_task.add_done_callback(self.publish_status_done)

    def publish_status_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("PLAYER_STATUS failed with exception: %s", exc)

    def tracks_changed(self, change):
        if isinstance(change, model_base.PropertyListInsert):
            self.add_track(change.new_value)
        elif isinstance(change, model_base.PropertyListDelete):
            self.remove_track(change.old_value)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def add_track(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            if isinstance(t, model.TrackGroup):
                self.group_listeners[t.id] = t.listeners.add(
                    'tracks', self.tracks_changed)
            else:
                self.track_entity_sources[t.id] = t.create_entity_source()

    def remove_track(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            if isinstance(t, model.TrackGroup):
                listener = self.group_listeners.pop(t.id)
                listener.remove()
            else:
                entity_source = self.track_entity_sources.pop(t.id)
                entity_source.close()

    def get_track_entities(self, entities, start_pos, end_pos, sample_pos_offset):
        for entity_source in self.track_entity_sources.values():
            entity_source.get_entities(entities, start_pos, end_pos, sample_pos_offset)

    def handle_pipeline_mutation(self, mutation):
        if self.pending_pipeline_mutations is not None:
            self.pending_pipeline_mutations.append(mutation)
        else:
            self.event_loop.create_task(
                self.publish_pipeline_mutation(mutation))

    async def publish_pipeline_mutation(self, mutation):
        if self.audioproc_client is None:
            return

        try:
            if isinstance(mutation, mutations.AddNode):
                await self.audioproc_client.add_node(
                    mutation.node_type, id=mutation.node_id,
                    name=mutation.node_name, **mutation.args)

            elif isinstance(mutation, mutations.RemoveNode):
                await self.audioproc_client.remove_node(mutation.node_id)

            elif isinstance(mutation, mutations.ConnectPorts):
                await self.audioproc_client.connect_ports(
                    mutation.src_node, mutation.src_port,
                    mutation.dest_node, mutation.dest_port)

            elif isinstance(mutation, mutations.DisconnectPorts):
                await self.audioproc_client.disconnect_ports(
                    mutation.src_node, mutation.src_port,
                    mutation.dest_node, mutation.dest_port)

            elif isinstance(mutation, mutations.SetPortProperty):
                await self.audioproc_client.set_port_property(
                    mutation.node, mutation.port, **mutation.kwargs)

            elif isinstance(mutation, mutations.SetNodeParameter):
                await self.audioproc_client.set_node_parameter(
                    mutation.node, **mutation.kwargs)

            else:
                raise ValueError(type(mutation))

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    async def update_settings(self, settings):
        self.proxy.update_settings(settings)

    def send_message(self, msg):
        self.proxy.send_message(msg)
