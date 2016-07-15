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
        timepos_offset = None

        while True:
            try:
                request = self._server.receive_frame()

                new_state = self._player.playback_state
                if state != new_state:
                    if new_state == 'playing':
                        timepos_offset = self._player.playback_timepos - request.timepos
                    state = new_state

                if state == 'playing':
                    for queue, event in self._player.get_track_events(
                            request.timepos - timepos_offset):
                        event.timepos += timepos_offset
                        request.events.append((queue, event))

                    self._player.playback_timepos += 4096

                self._client.send_frame(request)
                response = self._client.receive_frame()
                self._server.send_frame(response)

            except audioproc.StreamClosed:
                break


class Player(object):
    def __init__(self, sheet, manager, event_loop):
        self.sheet = sheet
        self.manager = manager
        self.event_loop = event_loop

        self.id = uuid.uuid4().hex
        self.server = ipc.Server(self.event_loop, 'player')

        self.setup_complete = False

        self.audioproc_address = None
        self.audioproc_client = None
        self.audiostream_address = None

        self.mutation_listener = None
        self.pending_pipeline_mutations = None

        self.proxy = None

        self.playback_state = 'stopped'
        self.playback_timepos = 0
        self.track_event_sources = {}
        self.tracks_listener = None

    @property
    def proxy_address(self):
        assert self.proxy is not None
        return self.proxy.address

    async def setup(self):
        await self.server.setup()

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

        for track in self.sheet.tracks:
            self.track_event_sources[track.id] = track.create_event_source()
        self.tracks_listener = self.sheet.listeners.add(
            'tracks', self.tracks_changed)

    async def cleanup(self):
        if self.tracks_listener is not None:
            self.tracks_listener.remove()
            self.tracks_listener = None

        self.track_event_sources.clear()

        if self.mutation_listener is not None:
            self.mutation_listener.remove()
            self.mutation_listener = None

        if self.proxy is not None:
            self.proxy.cleanup()
            self.proxy = None

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None
            self.audioproc_address = None
            self.audiostream_address = None

        await self.server.cleanup()

    def tracks_changed(self, change):
        if isinstance(change, model_base.PropertyListInsert):
            track = change.new_value
            self.track_event_sources[track.id] = track.create_event_source()

        elif isinstance(change, model_base.PropertyListDelete):
            track = change.old_value
            del self.track_event_sources[track.id]

        elif isinstance(change, model_base.PropertyListClear):
            self.track_event_sources.clear()

        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def get_track_events(self, timepos):
        events = []
        for track_id, event_source in self.track_event_sources.items():
            for event in event_source.get_events(timepos, timepos + 4096):
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

