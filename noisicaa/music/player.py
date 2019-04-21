#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
import concurrent.futures
import logging
import uuid
from typing import cast, Optional, Iterator, Iterable, Dict, Tuple

from noisicaa import core
from noisicaa.core import ipc
from noisicaa.core import session_data_pb2
from noisicaa import audioproc
from noisicaa import model
from . import pmodel
from . import node_connector

logger = logging.getLogger(__name__)


class Player(object):
    def __init__(
            self, *,
            project: pmodel.Project,
            event_loop: asyncio.AbstractEventLoop,
            audioproc_client: audioproc.AbstractAudioProcClient,
            realm: str,
            callback_address: Optional[str] = None
    ) -> None:
        self.project = project
        self.callback_address = callback_address
        self.event_loop = event_loop
        self.audioproc_client = audioproc_client
        self.realm = realm

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.id = uuid.uuid4().hex

        self.callback_stub = None  # type: ipc.Stub

        self.__node_connectors = {}  # type: Dict[int, node_connector.NodeConnector]

    async def setup(self) -> None:
        logger.info("Setting up player instance %s..", self.id)

        if self.callback_address is not None:
            logger.info("Connecting to client callback server %s..", self.callback_address)
            self.callback_stub = ipc.Stub(self.event_loop, self.callback_address)
            await self.callback_stub.connect()

        self.__listeners['pipeline_mutations'] = self.project.pipeline_mutation.add(
            self.handle_pipeline_mutation)

        logger.info("Populating realm with project state...")
        for mutation in self.project.get_add_mutations():
            await self.publish_pipeline_mutation(mutation)

        await self.audioproc_client.update_project_properties(
            self.realm,
            audioproc.ProjectProperties(
                bpm=self.project.bpm,
                duration=self.project.duration.to_proto()))

        messages = audioproc.ProcessorMessageList()
        for node in self.project.nodes:
            messages.messages.extend(self.add_node(node))
        await self.audioproc_client.send_node_messages(self.realm, messages)

        self.__listeners['project:nodes'] = self.project.nodes_changed.add(
            self.__on_project_nodes_changed)
        self.__listeners['project:bpm'] = self.project.bpm_changed.add(
            self.__on_project_bpm_changed)
        self.__listeners['project:duration'] = self.project.duration_changed.add(
            self.__on_project_duration_changed)

        logger.info("Player instance %s setup complete.", self.id)

    async def cleanup(self) -> None:
        logger.info("Cleaning up player instance %s..", self.id)

        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        if self.callback_stub is not None:
            logger.info("Closing connection to client callback server...")
            await self.callback_stub.close()
            self.callback_stub = None

        for connector in self.__node_connectors.values():
            connector.close()
        self.__node_connectors.clear()

        logger.info("Player instance %s cleanup complete.", self.id)

    def __on_project_bpm_changed(self, change: model.PropertyValueChange) -> None:
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(
                self.realm, audioproc.ProjectProperties(bpm=change.new_value)),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __on_project_duration_changed(self, change: model.PropertyValueChange) -> None:
        if self.audioproc_client is None:
            return

        callback_task = asyncio.run_coroutine_threadsafe(
            self.audioproc_client.update_project_properties(
                self.realm, audioproc.ProjectProperties(duration=change.new_value.to_proto())),
            self.event_loop)
        callback_task.add_done_callback(self.__update_project_properties_done)

    def __update_project_properties_done(self, callback_task: concurrent.futures.Future) -> None:
        assert callback_task.done()
        exc = callback_task.exception()
        if exc is not None:
            logger.error("UPDATE_PROJECT_PROPERTIES failed with exception: %s", exc)

    def __on_project_nodes_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyListInsert):
            messages = audioproc.ProcessorMessageList()
            messages.messages.extend(self.add_node(change.new_value))
            self.send_node_messages(messages)

        elif isinstance(change, model.PropertyListDelete):
            self.remove_node(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    async def set_session_values(self, values: Iterable[session_data_pb2.SessionValue]) -> None:
        await self.audioproc_client.set_session_values(self.realm, values)

    def add_node(self, node: pmodel.BaseNode) -> Iterator[audioproc.ProcessorMessage]:
        connector = cast(
            node_connector.NodeConnector,
            node.create_node_connector(
                message_cb=self.send_node_message, audioproc_client=self.audioproc_client))
        if connector is not None:
            yield from connector.init()
            self.__node_connectors[node.id] = connector

    def remove_node(self, node: pmodel.BaseNode) -> None:
        if node.id in self.__node_connectors:
            self.__node_connectors.pop(node.id).close()

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        self.event_loop.create_task(self.publish_pipeline_mutation(mutation))

    async def publish_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        if self.audioproc_client is None:
            return

        await self.audioproc_client.pipeline_mutation(self.realm, mutation)

    def send_node_message(self, msg: audioproc.ProcessorMessage) -> None:
        messages = audioproc.ProcessorMessageList()
        messages.messages.extend([msg])
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    def send_node_messages(self, messages: audioproc.ProcessorMessageList) -> None:
        self.event_loop.create_task(self.__send_node_messages_async(messages))

    async def __send_node_messages_async(self, messages: audioproc.ProcessorMessageList) -> None:
        if self.audioproc_client is None:
            return

        await self.audioproc_client.send_node_messages(self.realm, messages)

    async def update_state(self, state: audioproc.PlayerState) -> None:
        if self.audioproc_client is None:
            return

        assert not state.HasField('realm'), state
        state.realm = self.realm

        await self.audioproc_client.update_player_state(state)

    async def create_plugin_ui(self, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self.audioproc_client.create_plugin_ui(self.realm, node_id)

    async def delete_plugin_ui(self, node_id: str) -> None:
        await self.audioproc_client.delete_plugin_ui(self.realm, node_id)
