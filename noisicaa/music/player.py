#!/usr/bin/python3

import functools
import asyncio
import logging
import os.path
import random
import tempfile
import threading
import time
import uuid

from noisicaa import core
from noisicaa.core import ipc
from noisicaa.core import model_base
from noisicaa import audioproc
from noisicaa import music

from . import project
from . import mutations
from . import commands
from . import model

logger = logging.getLogger(__name__)


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
    def __init__(self, player, address, socket_dir=None):
        self._player = player

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'player.%s.pipe' % uuid.uuid4().hex)

        self._server = audioproc.AudioStreamServer(self.address)
        self._client = audioproc.AudioStreamClient(address)

        self._thread = threading.Thread(target=self.main)

    def setup(self):
        self._server.setup()
        self._client.setup()
        self._thread.start()

    def cleanup(self):
        self._thread.join()
        self._client.cleanup()
        self._server.cleanup()

    def main(self):
        state = 'stopped'
        sample_pos_offset = None

        while True:
            try:
                request = self._server.receive_frame()

                perf = core.PerfStats()

                new_state = self._player.playback_state
                if state != new_state:
                    if new_state == 'playing':
                        sample_pos_offset = request.sample_pos - self._player.playback_sample_pos
                    state = new_state

                if state == 'playing':
                    with perf.track('get_track_events'):
                        for queue, event in self._player.get_track_events(
                                request.sample_pos - sample_pos_offset,
                                request.duration):
                            event.sample_pos += sample_pos_offset
                            request.events.append((queue, event))

                    self._player.playback_sample_pos += request.duration

                with perf.track('send_frame'):
                    self._client.send_frame(request)
                with perf.track('receive_frame'):
                    response = self._client.receive_frame()
                perf.add_spans(response.perf_data)
                response.perf_data = perf.get_spans()
                if state == 'playing':
                    self._player.publish_status_async(
                        playback_pos=(
                            request.sample_pos - sample_pos_offset,
                            request.duration))
                self._server.send_frame(response)

            except audioproc.StreamClosed:
                break


class Player(object):
    def __init__(self, sheet, callback_address, manager, event_loop):
        self.sheet = sheet
        self.manager = manager
        self.callback_address = callback_address
        self.event_loop = event_loop

        self.id = uuid.uuid4().hex
        self.server = ipc.Server(self.event_loop, 'player')

        self.callback_stub = None

        self.setup_complete = False

        self.audioproc_address = None
        self.audioproc_client = None
        self.audiostream_address = None

        self.mutation_listener = None
        self.pending_pipeline_mutations = None

        self.proxy = None

        self.playback_state = 'stopped'
        self.playback_sample_pos = 0
        self.track_event_sources = {}
        self.group_listeners = {}

    @property
    def proxy_address(self):
        assert self.proxy is not None
        return self.proxy.address

    async def setup(self):
        await self.server.setup()

        self.callback_stub = ipc.Stub(
            self.event_loop, self.callback_address)
        await self.callback_stub.connect()

        self.audioproc_address = await self.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'player')
        self.audioproc_client = AudioProcClient(
            self.event_loop, self.server)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(self.audioproc_address)
        self.audiostream_address = await self.audioproc_client.set_backend('ipc')

        self.proxy = AudioStreamProxy(self, self.audiostream_address)
        self.proxy.setup()

        self.pending_pipeline_mutations = []
        self.mutation_listener = self.sheet.listeners.add(
            'pipeline_mutations', self.handle_pipeline_mutation)

        self.sheet.add_to_pipeline()
        pipeline_mutations = self.pending_pipeline_mutations[:]
        self.pending_pipeline_mutations = None

        for mutation in pipeline_mutations:
            await self.publish_pipeline_mutation(mutation)

        await self.audioproc_client.dump()

        self.add_track(self.sheet.master_group)

    async def cleanup(self):
        for listener in self.group_listeners.values():
            listener.remove()
        self.group_listeners.clear()

        self.track_event_sources.clear()

        if self.mutation_listener is not None:
            self.mutation_listener.remove()
            self.mutation_listener = None

        if self.proxy is not None:
            self.proxy.cleanup()
            self.proxy = None

        if self.callback_stub is not None:
            await self.callback_stub.close()
            self.callback_stub = None

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None
            self.audioproc_address = None
            self.audiostream_address = None

        await self.server.cleanup()

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
                self.track_event_sources[t.id] = t.create_event_source()

    def remove_track(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            if isinstance(t, model.TrackGroup):
                listener = self.group_listeners[t.id]
                listener.remove()
                del self.group_listeners[t.id]
            else:
                del self.track_event_sources[t.id]

    def get_track_events(self, sample_pos, num_samples):
        events = []
        for track_id, event_source in self.track_event_sources.items():
            for event in event_source.get_events(
                    sample_pos, sample_pos + num_samples):
                events.append(('track:%s' % track_id, event))
        return events

    def handle_pipeline_mutation(self, mutation):
        if self.pending_pipeline_mutations is not None:
            self.pending_pipeline_mutations.append(mutation)
        else:
            self.event_loop.create_task(
                self.publish_pipeline_mutation(mutation))

    async def publish_pipeline_mutation(self, mutation):
        if self.audioproc_client is None:
            return

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

        else:
            raise ValueError(type(mutation))

    def _set_playback_state(self, new_state):
        assert new_state in ('stopped', 'playing')
        if new_state == self.playback_state:
            return

        logger.info(
            "Change playback state %s -> %s.",
            self.playback_state, new_state)
        self.playback_state = new_state

    async def playback_start(self):
        self._set_playback_state('playing')

    async def playback_pause(self):
        self._set_playback_state('stopped')

    async def playback_stop(self):
        self._set_playback_state('stopped')

