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
import logging
import os
import os.path
from typing import Dict, List, Iterable

from noisicaa import core
from noisicaa.core import session_data_pb2

logger = logging.getLogger(__name__)


class SessionValueStore(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, session_name: str) -> None:
        self.__event_loop = event_loop
        self.__session_name = session_name

        self.__session_data = {}  # type: Dict[str, session_data_pb2.SessionValue]
        self.__session_data_path = None  # type: str

        self.values_changed = core.AsyncCallback[List[session_data_pb2.SessionValue]]()

    async def init(self, data_dir: str) -> None:
        self.__session_data = {}

        if data_dir is not None:
            self.__session_data_path = os.path.join(data_dir, 'sessions', self.__session_name)
            if not os.path.isdir(self.__session_data_path):
                os.makedirs(self.__session_data_path)

            checkpoint_path = os.path.join(self.__session_data_path, 'checkpoint')
            if os.path.isfile(checkpoint_path):
                checkpoint = session_data_pb2.SessionDataCheckpoint()
                with open(checkpoint_path, 'rb') as fp:
                    checkpoint_serialized = fp.read()

                # mypy thinks that ParseFromString has no return value. bug in the stubs?
                bytes_parsed = checkpoint.ParseFromString(checkpoint_serialized)  # type: ignore
                assert bytes_parsed == len(checkpoint_serialized)

                for session_value in checkpoint.session_values:
                    self.__session_data[session_value.name] = session_value

        await self.values_changed.call(self.values())

    def values(self) -> List[session_data_pb2.SessionValue]:
        return list(self.__session_data.values())

    async def set_values(
            self, session_values: Iterable[session_data_pb2.SessionValue],
    ) -> None:
        assert self.__session_data_path is not None

        changes = {}
        for session_value in session_values:
            if (session_value.name in self.__session_data
                    and self.__session_data[session_value.name] == session_value):
                continue
            changes[session_value.name] = session_value

        if not changes:
            return

        self.__session_data.update(changes)

        checkpoint = session_data_pb2.SessionDataCheckpoint(
            session_values=self.__session_data.values())
        with open(os.path.join(self.__session_data_path, 'checkpoint'), 'wb') as fp:
            fp.write(checkpoint.SerializeToString())

        await self.values_changed.call(list(changes.values()))

    async def set_value(self, session_value: session_data_pb2.SessionValue) -> None:
        await self.set_values([session_value])

    def set_value_async(self, session_value: session_data_pb2.SessionValue) -> None:
        self.__event_loop.create_task(self.set_values([session_value]))
