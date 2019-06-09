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

import logging
from typing import Any

from noisicaa import core
from noisicaa.core import storage
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from . import writer_process_pb2

logger = logging.getLogger(__name__)


class WriterProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__storage = None  # type: storage.ProjectStorage

    async def setup(self) -> None:
        await super().setup()

        endpoint = ipc.ServerEndpoint('main')
        endpoint.add_handler(
            'CREATE', self.__handle_create,
            writer_process_pb2.CreateRequest, writer_process_pb2.CreateResponse)
        endpoint.add_handler(
            'OPEN', self.__handle_open,
            writer_process_pb2.OpenRequest, writer_process_pb2.OpenResponse)
        endpoint.add_handler(
            'CLOSE', self.__handle_close,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        endpoint.add_handler(
            'WRITE_LOG', self.__handle_write_log,
            writer_process_pb2.WriteLogRequest, writer_process_pb2.WriteResponse)
        endpoint.add_handler(
            'WRITE_CHECKPOINT', self.__handle_write_checkpoint,
            writer_process_pb2.WriteCheckpointRequest, writer_process_pb2.WriteResponse)
        endpoint.add_handler(
            'UNDO', self.__handle_undo,
            empty_message_pb2.EmptyMessage, writer_process_pb2.UndoResponse)
        endpoint.add_handler(
            'REDO', self.__handle_redo,
            empty_message_pb2.EmptyMessage, writer_process_pb2.RedoResponse)
        await self.server.add_endpoint(endpoint)

    async def cleanup(self) -> None:
        if self.__storage is not None:
            self.__storage.close()
            self.__storage = None

        await super().cleanup()

    def __get_storage_state(self) -> writer_process_pb2.StorageState:
        return writer_process_pb2.StorageState(
            can_undo=self.__storage.can_undo,
            can_redo=self.__storage.can_redo,
        )

    async def __handle_create(
            self,
            request: writer_process_pb2.CreateRequest,
            response: writer_process_pb2.CreateResponse,
    ) -> None:
        assert self.__storage is None

        self.__storage = storage.ProjectStorage.create(request.path)
        response.data_dir = self.__storage.path
        self.__storage.add_checkpoint(request.initial_checkpoint)

        response.storage_state.CopyFrom(self.__get_storage_state())

    async def __handle_open(
            self,
            request: writer_process_pb2.OpenRequest,
            response: writer_process_pb2.OpenResponse,
    ) -> None:
        assert self.__storage is None

        self.__storage = storage.ProjectStorage()
        self.__storage.open(request.path)
        response.data_dir = self.__storage.path

        checkpoint_number, actions = self.__storage.get_restore_info()

        response.checkpoint = self.__storage.get_checkpoint(checkpoint_number)

        for action, log_number in actions:
            sequence_data = self.__storage.get_log_entry(log_number)
            response.actions.add(
                direction={
                    storage.ACTION_FORWARD: writer_process_pb2.Action.FORWARD,
                    storage.ACTION_BACKWARD: writer_process_pb2.Action.BACKWARD,
                }[action],
                data=sequence_data)

        response.storage_state.CopyFrom(self.__get_storage_state())

    async def __handle_close(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage,
    ) -> None:
        if self.__storage is not None:
            self.__storage.close()
            self.__storage = None

    async def __handle_write_log(
            self,
            request: writer_process_pb2.WriteLogRequest,
            response: writer_process_pb2.WriteResponse,
    ) -> Any:
        assert self.__storage is not None

        self.__storage.append_log_entry(request.log)

        response.storage_state.CopyFrom(self.__get_storage_state())

    async def __handle_write_checkpoint(
            self,
            request: writer_process_pb2.WriteCheckpointRequest,
            response: writer_process_pb2.WriteResponse,
    ) -> Any:
        assert self.__storage is not None

        self.__storage.add_checkpoint(request.checkpoint)

        response.storage_state.CopyFrom(self.__get_storage_state())

    async def __handle_undo(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: writer_process_pb2.UndoResponse,
    ) -> None:
        assert self.__storage is not None

        if self.__storage.can_undo:
            action, sequence_data = self.__storage.get_log_entry_to_undo()
            self.__storage.undo()

            response.action.direction = {
                storage.ACTION_FORWARD: writer_process_pb2.Action.FORWARD,
                storage.ACTION_BACKWARD: writer_process_pb2.Action.BACKWARD,
            }[action]
            response.action.data = sequence_data

        response.storage_state.CopyFrom(self.__get_storage_state())

    async def __handle_redo(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: writer_process_pb2.RedoResponse,
    ) -> None:
        assert self.__storage is not None

        if self.__storage.can_redo:
            action, sequence_data = self.__storage.get_log_entry_to_redo()
            self.__storage.redo()

            response.action.direction = {
                storage.ACTION_FORWARD: writer_process_pb2.Action.FORWARD,
                storage.ACTION_BACKWARD: writer_process_pb2.Action.BACKWARD,
            }[action]
            response.action.data = sequence_data

        response.storage_state.CopyFrom(self.__get_storage_state())


class WriterSubprocess(core.SubprocessMixin, WriterProcess):
    pass
