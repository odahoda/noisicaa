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

# mypy: loose

import asyncio
import logging
import uuid
from typing import Dict  # pylint: disable=unused-import

from noisicaa import core
from noisicaa.core import ipc
from noisicaa.core import model_base
from noisicaa import audioproc

from . import model
from . import track_group
from . import base_track  # pylint: disable=unused-import

logger = logging.getLogger(__name__)


class Player(object):
    def __init__(self, *,
                 project, event_loop, audioproc_client, realm,
                 callback_address=None):
        self.project = project
        self.callback_address = callback_address
        self.event_loop = event_loop
        self.audioproc_client = audioproc_client
        self.realm = realm

        self.listeners = core.CallbackRegistry()
        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.id = uuid.uuid4().hex

        self.callback_stub = None  # ipc.Stub

        self.track_connectors = {}  # type: Dict[str, base_track.TrackConnector]

    async def setup(self):
        logger.info("Setting up player instance %s..", self.id)

        if self.callback_address is not None:
            logger.info("Connecting to client callback server %s..", self.callback_address)
            self.callback_stub = ipc.Stub(self.event_loop, self.callback_address)
            await self.callback_stub.connect()

        self.__listeners['pipeline_mutations'] = self.project.listeners.add(
            'pipeline_mutations', self.handle_pipeline_mutation)
        self.__listeners['player_state'] = self.audioproc_client.listeners.add(
            'player_state', self.__handle_player_state)

        logger.info("Populating realm with project state...")
        for mutation in self.project.get_add_mutations():
            await self.publish_pipeline_mutation(mutation)

        await self.audioproc_client.update_project_properties(
            self.realm,
            bpm=self.project.bpm,
            duration=self.project.duration)

        messages = audioproc.ProcessorMessageList()
        messages.messages.extend(self.add_track(self.project.master_group))
        await self.audioproc_client.send_node_messages(
            self.realm, messages)

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

        if self.callback_stub is not None:
            logger.info("Closing connection to client callback server...")
            await self.callback_stub.close()
            self.callback_stub = None

        for connector in self.track_connectors.values():
            connector.close()
        self.track_connectors.clear()

        logger.info("Player instance %s cleanup complete.", self.id)

    def __on_project_bpm_changed(self, change):
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(
                self.realm, bpm=change.new_value),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __on_project_duration_changed(self, change):
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(
                self.realm, duration=change.new_value),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __update_project_properties_done(self, callback_task):
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("UPDATE_PROJECT_PROPERTIES failed with exception: %s", exc)

    def __handle_player_state(self, realm, state):
        self.listeners.call('player_state', state)
        self.publish_status_async(player_state=state)

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
            if isinstance(t, track_group.TrackGroup):
                self.__listeners['track_group:%s' % t.id] = t.listeners.add(
                    'tracks', self.tracks_changed)
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

        await self.audioproc_client.pipeline_mutation(self.realm, mutation)

    def send_node_message(self, msg):
        messages = audioproc.ProcessorMessageList()
        messages.messages.extend([msg])
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    def send_node_messages(self, messages):
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    async def __send_node_messages_async(self, messages):
        if self.audioproc_client is None:
            return

        await self.audioproc_client.send_node_messages(self.realm, messages)

    async def update_state(self, state):
        if self.audioproc_client is None:
            return

        await self.audioproc_client.update_player_state(self.realm, state)

    def send_message(self, msg):
        # TODO: reimplement this.
        pass

    async def create_plugin_ui(self, node_id):
        return await self.audioproc_client.create_plugin_ui(self.realm, node_id)

    async def delete_plugin_ui(self, node_id):
        return await self.audioproc_client.delete_plugin_ui(self.realm, node_id)
