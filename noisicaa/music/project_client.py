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
from fractions import Fraction
import getpass
import logging
import socket
from typing import cast, Any, Dict, Tuple, Callable, Iterable, Type, TypeVar  # pylint: disable=unused-import

from noisicaa import audioproc
from noisicaa import core
from noisicaa import node_db as node_db_lib
from noisicaa.core import ipc

from . import mutations as mutations_lib
from . import render_settings_pb2

logger = logging.getLogger(__name__)


class ObjectProxy(core.ObjectBase):
    def __init__(self, *, obj_id: str) -> None:
        super().__init__()
        self.state['id'] = obj_id
        self.listeners = core.CallbackRegistry()

    def property_changed(self, change: core.PropertyChange) -> None:
        if isinstance(change, core.PropertyValueChange):
            self.listeners.call(
                change.prop_name, change.old_value, change.new_value)

        elif isinstance(change, core.PropertyListInsert):
            self.listeners.call(
                change.prop_name, 'insert',
                change.index, change.new_value)

        elif isinstance(change, core.PropertyListDelete):
            self.listeners.call(
                change.prop_name, 'delete',
                change.index, change.old_value)

        else:
            raise TypeError("Unsupported change type %s" % type(change))


class ProjectProxy(ObjectProxy):
    def init(self, node_db: node_db_lib.NodeDBClient, obj_map: Dict[str, ObjectProxy]) -> None:
        raise NotImplementedError


class ProjectClient(object):
    def __init__(
            self, event_loop: asyncio.AbstractEventLoop, tmp_dir: str,
            node_db: node_db_lib.NodeDBClient = None) -> None:
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client', socket_dir=tmp_dir)
        self._node_db = node_db
        self._stub = None  # type: ipc.Stub
        self._session_id = None  # type: str
        self._session_data = {}  # type: Dict[str, Any]
        self._object_map = {}  # type: Dict[str, ObjectProxy]
        self.project = None  # type: ProjectProxy
        self.cls_map = {}  # type: Dict[str, Type[ObjectProxy]]
        self.listeners = core.CallbackRegistry()

    def __set_project(self, root_id: str) -> None:
        assert self.project is None
        self.project = cast(ProjectProxy, self._object_map[root_id])
        self.project.init(self._node_db, self._object_map)

    async def setup(self) -> None:
        await self.server.setup()
        self.server.add_command_handler(
            'PROJECT_MUTATIONS', self.handle_project_mutations)
        self.server.add_command_handler(
            'PROJECT_CLOSED', self.handle_project_closed)
        self.server.add_command_handler(
            'PLAYER_STATUS', self.handle_player_status,
            log_level=-1)
        self.server.add_command_handler(
            'SESSION_DATA_MUTATION', self.handle_session_data_mutation)

    async def cleanup(self) -> None:
        await self.disconnect()
        await self.server.cleanup()

    async def connect(self, address: str) -> None:
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_data = {}
        session_name = '%s.%s' % (getpass.getuser(), socket.getfqdn())
        self._session_id = await self._stub.call('START_SESSION', self.server.address, session_name)
        root_id = await self._stub.call('GET_ROOT_ID', self._session_id)
        if root_id is not None:
            # Connected to a loaded project.
            self.__set_project(root_id)

    async def disconnect(self, shutdown: bool = False) -> None:
        if self._session_id is not None:
            try:
                await self._stub.call('END_SESSION', self._session_id)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
            self._session_id = None

        if self._stub is not None:
            if shutdown:
                await self.shutdown()

            await self._stub.close()
            self._stub = None

    def apply_properties(
            self, obj: ObjectProxy, properties: Iterable[Tuple[str, str, Any]]) -> None:
        for prop_name, prop_type, value in properties:
            if prop_type == 'scalar':
                setattr(obj, prop_name, value)

            elif prop_type == 'list':
                lst = getattr(obj, prop_name)
                lst.clear()
                lst.extend(value)

            elif prop_type == 'obj':
                child = None
                if value is not None:
                    child = self._object_map[value]
                setattr(obj, prop_name, child)

            elif prop_type == 'objlist':
                lst = getattr(obj, prop_name)
                lst.clear()
                for child_id in value:
                    child = self._object_map[child_id]
                    lst.append(child)

            else:
                raise ValueError(
                    "Property type %s not supported." % prop_type)

    def handle_project_mutations(self, mutations: Iterable[mutations_lib.Mutation]) -> None:
        for mutation in mutations:
            self.handle_project_mutation(mutation)

    def handle_project_mutation(self, mutation: mutations_lib.Mutation) -> None:
        logger.info("Mutation received: %s", mutation)

        if isinstance(mutation, mutations_lib.SetProperties):
            obj = self._object_map[mutation.id]
            self.apply_properties(obj, mutation.properties)

        elif isinstance(mutation, mutations_lib.AddObject):
            cls = self.cls_map[mutation.cls]
            obj = cls(obj_id=mutation.id)
            self.apply_properties(obj, mutation.properties)
            self._object_map[mutation.id] = obj

        elif isinstance(mutation, mutations_lib.ListInsert):
            obj = self._object_map[mutation.id]
            lst = getattr(obj, mutation.prop_name)
            if mutation.value_type == 'obj':
                child = self._object_map[mutation.value]
                lst.insert(mutation.index, child)
            elif mutation.value_type == 'scalar':
                lst.insert(mutation.index, mutation.value)
            else:
                raise ValueError(
                    "Value type %s not supported."
                    % mutation.value_type)

        elif isinstance(mutation, mutations_lib.ListDelete):
            obj = self._object_map[mutation.id]
            lst = getattr(obj, mutation.prop_name)
            del lst[mutation.index]

        else:
            raise ValueError("Unknown mutation %s received." % mutation)

    def handle_project_closed(self) -> None:
        logger.info("Project closed received.")

    async def shutdown(self) -> None:
        await self._stub.call('SHUTDOWN')

    async def test(self) -> None:
        await self._stub.call('TEST')

    async def create(self, path: str) -> None:
        assert self.project is None
        root_id = await self._stub.call('CREATE', self._session_id, path)
        self.__set_project(root_id)

    async def create_inmemory(self) -> None:
        assert self.project is None
        root_id = await self._stub.call('CREATE_INMEMORY', self._session_id)
        self.__set_project(root_id)

    async def open(self, path: str) -> None:
        assert self.project is None
        root_id = await self._stub.call('OPEN', self._session_id, path)
        self.__set_project(root_id)

    async def close(self) -> None:
        assert self.project is not None
        await self._stub.call('CLOSE')
        self.project = None
        self._object_map.clear()

    async def send_command(self, target: str, command: str, **kwargs: Any) -> Any:
        assert self.project is not None
        result = await self._stub.call('COMMAND', target, command, kwargs)
        logger.info("Command %s completed with result=%r", command, result)
        return result

    async def undo(self) -> None:
        assert self.project is not None
        await self._stub.call('UNDO')

    async def redo(self) -> None:
        assert self.project is not None
        await self._stub.call('REDO')

    async def serialize(self, obj_id: str) -> bytes:
        assert self.project is not None
        return await self._stub.call('SERIALIZE', self._session_id, obj_id)

    async def create_player(self, *, audioproc_address: str) -> Tuple[str, str]:
        return await self._stub.call(
            'CREATE_PLAYER', self._session_id,
            client_address=self.server.address,
            audioproc_address=audioproc_address)

    async def delete_player(self, player_id: str) -> None:
        await self._stub.call('DELETE_PLAYER', self._session_id, player_id)

    async def create_plugin_ui(self, player_id: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self._stub.call('CREATE_PLUGIN_UI', self._session_id, player_id, node_id)

    async def delete_plugin_ui(self, player_id: str, node_id: str) -> None:
        await self._stub.call('DELETE_PLUGIN_UI', self._session_id, player_id, node_id)

    async def update_player_state(self, player_id: str, state: audioproc.PlayerState) -> None:
        await self._stub.call('UPDATE_PLAYER_STATE', self._session_id, player_id, state)

    async def player_send_message(self, player_id: str, msg: Any) -> None:
        await self._stub.call('PLAYER_SEND_MESSAGE', self._session_id, player_id, msg.to_bytes())

    async def restart_player_pipeline(self, player_id: str) -> None:
        await self._stub.call('RESTART_PLAYER_PIPELINE', self._session_id, player_id)

    def add_player_status_listener(
            self, player_id: str, callback: Callable[..., None]
    ) -> core.Listener:
        return self.listeners.add('player_status:%s' % player_id, callback)

    async def handle_player_status(self, player_id: str, args: Dict[str, Any]) -> None:
        self.listeners.call('player_status:%s' % player_id, **args)

    async def dump(self) -> None:
        await self._stub.call('DUMP', self._session_id)

    async def render(
            self, callback_address: str, render_settings: render_settings_pb2.RenderSettings
    ) -> None:
        await self._stub.call('RENDER', self._session_id, callback_address, render_settings)

    async def handle_session_data_mutation(self, data: Dict[str, Any]) -> None:
        for key, value in data.items():
            if key not in self._session_data or self._session_data[key] != value:
                self._session_data[key] = value
                self.listeners.call('session_data:%s' % key, value)

    def set_session_values(self, data: Dict[str, Any]) -> None:
        assert isinstance(data, dict), data
        for key, value in data.items():
            assert isinstance(key, str), key
            assert isinstance(
                value,
                (str, bytes, bool, int, float, Fraction, audioproc.MusicalTime,
                 audioproc.MusicalDuration)), value

        self._session_data.update(data)
        self.event_loop.create_task(
            self._stub.call('SET_SESSION_VALUES', self._session_id, data))

    T = TypeVar('T')
    def get_session_value(self, key: str, default: T) -> T:  # pylint: disable=undefined-variable
        return self._session_data.get(key, default)
