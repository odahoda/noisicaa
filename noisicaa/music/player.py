#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import asyncio
import enum
import logging
import os
import os.path
import time
import uuid

import posix_ipc

from noisicaa import core
from noisicaa.core import ipc
from noisicaa.core import model_base
from noisicaa import audioproc

from . import model

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
        task = self._event_loop.create_task(self.backend_started())
        task.add_done_callback(self._backend_started_finished)

    def _backend_started_finished(self, task):
        exc = task.exception()
        if exc is not None:
            raise exc

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
        task = self._event_loop.create_task(self.backend_stopped())
        task.add_done_callback(self._backend_stopped_finished)

    def _backend_stopped_finished(self, task):
        exc = task.exception()
        if exc is not None:
            raise exc

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


class Player(object):
    def __init__(self, *,
                 project, manager, event_loop, tmp_dir,
                 callback_address=None, backend_type='ipc', datastream_address=None):
        self.project = project
        self.manager = manager
        self.callback_address = callback_address
        self.event_loop = event_loop
        self.backend_type = backend_type
        self.datastream_address = datastream_address

        self.listeners = core.CallbackRegistry()
        self.__listeners = {}

        self.id = uuid.uuid4().hex
        self.server = ipc.Server(self.event_loop, 'player', socket_dir=tmp_dir)

        self.callback_stub = None

        self.audioproc_backend = None
        self.audioproc_backend_last_crash_time = None
        self.audioproc_address = None
        self.audioproc_client = None
        self.audioproc_status_listener = None
        self.audioproc_player_state_listener = None
        self.audioproc_ready = None
        self.audiostream_address = os.path.join(tmp_dir, 'audiostream.%s.pipe' % uuid.uuid4().hex)

        self.track_connectors = {}

    async def setup(self):
        logger.info("Setting up player instance %s..", self.id)

        logger.info("Setting up player server...")
        await self.server.setup()
        logger.info("Player server address: %s", self.server.address)

        if self.callback_address is not None:
            logger.info("Connecting to client callback server %s..", self.callback_address)
            self.callback_stub = ipc.Stub(self.event_loop, self.callback_address)
            await self.callback_stub.connect()

        self.__listeners['pipeline_mutations'] = self.project.listeners.add(
            'pipeline_mutations', self.handle_pipeline_mutation)

        self.audioproc_shm = posix_ipc.SharedMemory(
            '/noisicaa-player.%s' % self.id,
            posix_ipc.O_CREAT | posix_ipc.O_EXCL,
            size=1024)

        logger.info("Starting audio process...")
        self.audioproc_ready = asyncio.Event(loop=self.event_loop)
        self.audioproc_backend = AudioProcBackend(self, self.event_loop)
        self.__listeners['audioproc_backend_state'] = self.audioproc_backend.add_state_listener(
            self.audioproc_state_changed)
        self.audioproc_backend.start()

        # TODO: with timeout
        await self.audioproc_ready.wait()

        self.__listeners['project:bpm'] = self.project.listeners.add(
            'bpm', self.__on_project_bpm_changed)
        self.__listeners['project:duration'] = self.project.listeners.add(
            'duration', self.__on_project_duration_changed)

        logger.info("Player instance %s setup complete.", self.id)

    async def cleanup(self):
        logger.info("Cleaning up player instance %s..", self.id)

        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

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

        for connector in self.track_connectors.values():
            connector.close()
        self.track_connectors.clear()

        logger.info("Cleaning up player server...")
        await self.server.cleanup()

        logger.info("Player instance %s cleanup complete.", self.id)

    def __on_project_bpm_changed(self, change):
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(bpm=change.new_value),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __on_project_duration_changed(self, change):
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(duration=change.new_value),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __update_project_properties_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("UPDATE_PROJECT_PROPERTIES failed with exception: %s", exc)

    def audioproc_state_changed(self, state):
        self.listeners.call('pipeline_status', {'pipeline_state': state.value})
        self.publish_status_async(pipeline_state=state.value)

    def __handle_pipeline_status(self, status):
        self.listeners.call('pipeline_status', status)

    def __handle_player_state(self, state):
        self.listeners.call('player_state', state)
        self.publish_status_async(player_state=state)

    async def start_audioproc(self):
        logger.info("Starting audioproc backend...")

        logger.info("Creating audioproc process...")
        self.audioproc_address = await self.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'player',
            shm=self.audioproc_shm.name,
            enable_player=True)

        logger.info("Creating audioproc client...")
        self.audioproc_client = AudioProcClient(
            self.event_loop, self.server)
        self.audioproc_status_listener = self.audioproc_client.listeners.add(
            'pipeline_status', self.__handle_pipeline_status)
        self.audioproc_player_state_listener = self.audioproc_client.listeners.add(
            'player_state', self.__handle_player_state)
        await self.audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await self.audioproc_client.connect(self.audioproc_address)

        logger.info("Setting backend...")
        if self.backend_type == 'ipc':
            await self.audioproc_client.set_backend(
                'ipc', ipc_address=self.audiostream_address)
        else:
            assert self.backend_type == 'renderer'
            assert self.datastream_address is not None
            await self.audioproc_client.set_backend(
                'renderer', datastream_address=self.datastream_address)

        logger.info("Audioproc backend started.")

    async def audioproc_started(self):
        try:
            for mutation in self.project.get_add_mutations():
                await self.publish_pipeline_mutation(mutation)

            await self.audioproc_client.dump()

            await self.audioproc_client.update_project_properties(
                bpm=self.project.bpm,
                duration=self.project.duration)

            messages = audioproc.ProcessorMessageList()
            messages.messages.extend(self.add_track(self.project.master_group))
            await self.audioproc_client.send_node_messages(messages)

            # TODO: Notify client (UI) about new stream address.

            self.audioproc_ready.set()

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    async def stop_audioproc(self):
        logger.info("Stopping audioproc backend...")

        if self.audioproc_player_state_listener is not None:
            self.audioproc_player_state_listener.remove()
            self.audioproc_player_state_listener = None

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

        logger.info("Audioproc backend stopped.")

    async def audioproc_stopped(self):
        self.remove_track(self.project.master_group)

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
        if self.callback_stub is None:
            return

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
            messages = audioproc.ProcessorMessageList()
            messages.messages.extend(self.add_track(change.new_value))
            self.send_node_messages(messages)

        elif isinstance(change, model_base.PropertyListDelete):
            self.remove_track(change.old_value)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def add_track(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            if isinstance(t, model.TrackGroup):
                self.__listeners['track_group:%s' % t.id] = t.listeners.add('tracks', self.tracks_changed)
            else:
                connector = t.create_track_connector(message_cb=self.send_node_message)
                yield from connector.init()
                self.track_connectors[t.id] = connector

    def remove_track(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            if isinstance(t, model.TrackGroup):
                self.__listeners.pop('track_group:%s' % t.id).remove()
            else:
                self.track_connectors.pop(t.id).close()

    def handle_pipeline_mutation(self, mutation):
        self.event_loop.create_task(self.publish_pipeline_mutation(mutation))

    async def publish_pipeline_mutation(self, mutation):
        if self.audioproc_client is None:
            return

        try:
            await self.audioproc_client.pipeline_mutation(mutation)

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    def send_node_message(self, msg):
        messages = audioproc.ProcessorMessageList()
        messages.messages.extend([msg])
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    def send_node_messages(self, messages):
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    async def __send_node_messages_async(self, messages):
        if self.audioproc_client is None:
            return

        try:
            await self.audioproc_client.send_node_messages(messages)

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    async def update_state(self, state):
        if self.audioproc_client is None:
            return

        try:
            await self.audioproc_client.update_player_state(state)

        except ipc.ConnectionClosed:
            self.audioproc_backend.backend_crashed()

    def send_message(self, msg):
        # TODO: reimplement this.
        pass
