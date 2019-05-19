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
import functools
import logging
import uuid
from typing import Optional, Dict, List, Tuple

from google.protobuf import message as protobuf

from noisicaa.core import ipc
from noisicaa.core import storage
from . import writer_process_pb2

logger = logging.getLogger(__name__)


class WriterClient(object):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self.__event_loop = event_loop

        self.__stub = None  # type: ipc.Stub
        self.__opened = False
        self.__path = None  # type: str
        self.__data_dir = None  # type: str
        self.__can_undo = None  # type: bool
        self.__can_redo = None  # type: bool
        self.__pending_writes = {}  # type: Dict[str, asyncio.Task]
        self.__write_queue_empty = asyncio.Event(loop=self.__event_loop)

    @property
    def path(self) -> str:
        assert self.__path is not None
        return self.__path

    @property
    def data_dir(self) -> str:
        assert self.__data_dir is not None
        return self.__data_dir

    @property
    def can_undo(self) -> bool:
        assert self.__can_undo is not None
        return self.__can_undo

    @property
    def can_redo(self) -> bool:
        assert self.__can_redo is not None
        return self.__can_redo

    def __update_storage_state(self, state: writer_process_pb2.StorageState) -> None:
        self.__can_undo = state.can_undo
        self.__can_redo = state.can_redo

    async def setup(self) -> None:
        self.__pending_writes.clear()
        self.__write_queue_empty.clear()

    async def cleanup(self) -> None:
        await self.disconnect()

    async def connect(self, address: str) -> None:
        assert self.__stub is None

        self.__stub = ipc.Stub(self.__event_loop, address)
        await self.__stub.connect()

    async def disconnect(self) -> None:
        if self.__stub is not None:
            await self.__stub.close()
            self.__stub = None

        self.__opened = False
        self.__path = None
        self.__data_dir = None

    async def create(self, path: str, initial_checkpoint: bytes) -> None:
        assert not self.__opened

        request = writer_process_pb2.CreateRequest(
            path=path,
            initial_checkpoint=initial_checkpoint)
        response = writer_process_pb2.CreateResponse()
        await self.__stub.call('CREATE', request, response)

        self.__opened = True
        self.__path = path
        self.__data_dir = response.data_dir
        self.__update_storage_state(response.storage_state)

    async def open(self, path: str) -> Tuple[bytes, List[Tuple[storage.Action, bytes]]]:
        assert not self.__opened

        request = writer_process_pb2.OpenRequest(
            path=path)
        response = writer_process_pb2.OpenResponse()
        await self.__stub.call('OPEN', request, response)

        self.__opened = True
        self.__path = path
        self.__data_dir = response.data_dir
        self.__update_storage_state(response.storage_state)

        return (
            response.checkpoint,
            [({writer_process_pb2.Action.FORWARD: storage.ACTION_FORWARD,
               writer_process_pb2.Action.BACKWARD: storage.ACTION_BACKWARD}[action.direction],
              action.data)
             for action in response.actions])

    async def close(self) -> None:
        if self.__opened:
            await self.flush()
            await self.__stub.call('CLOSE')
            self.__opened = False
            self.__path = None
            self.__data_dir = None

    async def flush(self) -> None:
        if len(self.__pending_writes) > 0:
            logger.info("Waiting for %d pending writes to complete...", len(self.__pending_writes))
            await self.__write_queue_empty.wait()
        assert len(self.__pending_writes) == 0

    def __write(
            self,
            method: str,
            request: protobuf.Message,
            response: writer_process_pb2.WriteResponse
    ) -> None:
        task_id = uuid.uuid4().hex
        task = self.__event_loop.create_task(self.__stub.call(method, request))
        task.add_done_callback(functools.partial(self.__write_done, task_id, response))
        self.__pending_writes[task_id] = task
        self.__write_queue_empty.clear()

    def __write_done(
            self,
            task_id: str,
            response: writer_process_pb2.WriteResponse,
            task: asyncio.Task
    ) -> None:
        self.__update_storage_state(response.storage_state)
        del self.__pending_writes[task_id]
        if len(self.__pending_writes) == 0:
            self.__write_queue_empty.set()

    def write_log(self, log: bytes) -> None:
        assert self.__opened

        request = writer_process_pb2.WriteLogRequest(
            log=log)
        response = writer_process_pb2.WriteResponse()
        self.__write('WRITE_LOG', request, response)

    def write_checkpoint(self, checkpoint: bytes) -> None:
        assert self.__opened

        request = writer_process_pb2.WriteCheckpointRequest(
            checkpoint=checkpoint)
        response = writer_process_pb2.WriteResponse()
        self.__write('WRITE_CHECKPOINT', request, response)

    async def undo(self) -> Optional[Tuple[storage.Action, bytes]]:
        assert self.__opened

        await self.flush()
        response = writer_process_pb2.UndoResponse()
        await self.__stub.call('UNDO', None, response)
        self.__update_storage_state(response.storage_state)

        if not response.HasField('action'):
            return None

        return (
            {writer_process_pb2.Action.FORWARD: storage.ACTION_FORWARD,
             writer_process_pb2.Action.BACKWARD: storage.ACTION_BACKWARD
            }[response.action.direction],
            response.action.data)

    async def redo(self) -> Optional[Tuple[storage.Action, bytes]]:
        assert self.__opened

        await self.flush()
        response = writer_process_pb2.RedoResponse()
        await self.__stub.call('REDO', None, response)
        self.__update_storage_state(response.storage_state)

        if not response.HasField('action'):
            return None

        return (
            {writer_process_pb2.Action.FORWARD: storage.ACTION_FORWARD,
             writer_process_pb2.Action.BACKWARD: storage.ACTION_BACKWARD
            }[response.action.direction],
            response.action.data)
