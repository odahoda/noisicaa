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
from fractions import Fraction
import getpass
import logging
import socket
from typing import cast, Any, Dict, Tuple, Callable, TypeVar

from noisicaa import audioproc
from noisicaa import core
from noisicaa import model
from noisicaa import node_db as node_db_lib
from noisicaa.core import ipc
from noisicaa.builtin_nodes import client_registry
from . import mutations as mutations_lib
from . import mutations_pb2
from . import render_settings_pb2
from . import commands_pb2
from . import project_client_model

logger = logging.getLogger(__name__)


class Pool(model.Pool[project_client_model.ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.register_class(project_client_model.Project)
        self.register_class(project_client_model.MeasureReference)
        self.register_class(project_client_model.Metadata)
        self.register_class(project_client_model.Sample)
        self.register_class(project_client_model.PipelineGraphConnection)
        self.register_class(project_client_model.PipelineGraphNode)
        self.register_class(project_client_model.SystemOutPipelineGraphNode)
        self.register_class(project_client_model.PipelineGraphControlValue)
        client_registry.register_classes(self)


class ProjectClient(object):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            tmp_dir: str,
            node_db: node_db_lib.NodeDBClient = None) -> None:
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client', socket_dir=tmp_dir)
        self._node_db = node_db
        self._stub = None  # type: ipc.Stub
        self._session_id = None  # type: str
        self._session_data = None  # type: Dict[str, Any]
        self.__pool = None  # type: Pool
        self.__session_data_listeners = core.CallbackMap[str, Any]()

    @property
    def project(self) -> project_client_model.Project:
        return cast(project_client_model.Project, self.__pool.root)

    def __set_project(self, root_id: int) -> None:
        project = cast(project_client_model.Project, self.__pool[root_id])
        self.__pool.set_root(project)
        project.init(self._node_db)

    async def setup(self) -> None:
        await self.server.setup()
        self.server.add_command_handler(
            'PROJECT_MUTATIONS', self.handle_project_mutations)
        self.server.add_command_handler(
            'PROJECT_CLOSED', self.handle_project_closed)
        self.server.add_command_handler(
            'SESSION_DATA_MUTATION', self.handle_session_data_mutation)

    async def cleanup(self) -> None:
        await self.disconnect()
        await self.server.cleanup()

    async def connect(self, address: str) -> None:
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()

        self.__pool = Pool()
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

    def get_object(self, obj_id: int) -> project_client_model.ObjectBase:
        return self.__pool[obj_id]

    def handle_project_mutations(self, mutations: mutations_pb2.MutationList) -> None:
        mutation_list = mutations_lib.MutationList(self.__pool, mutations)
        mutation_list.apply_forward()

    def handle_project_closed(self) -> None:
        logger.info("Project closed received.")

    async def shutdown(self) -> None:
        await self._stub.call('SHUTDOWN')

    async def test(self) -> None:
        await self._stub.call('TEST')

    async def create(self, path: str) -> None:
        root_id = await self._stub.call('CREATE', self._session_id, path)
        self.__set_project(root_id)

    async def create_inmemory(self) -> None:
        root_id = await self._stub.call('CREATE_INMEMORY', self._session_id)
        self.__set_project(root_id)

    async def open(self, path: str) -> None:
        root_id = await self._stub.call('OPEN', self._session_id, path)
        self.__set_project(root_id)

    async def close(self) -> None:
        assert self.__pool is not None
        await self._stub.call('CLOSE')
        self.__pool = None

    async def send_command(self, command: commands_pb2.Command) -> Any:
        assert self.project is not None
        result = await self._stub.call('COMMAND', command)
        logger.info("Command %s completed with result=%r", command.command, result)
        return result

    async def undo(self) -> None:
        assert self.project is not None
        await self._stub.call('UNDO')

    async def redo(self) -> None:
        assert self.project is not None
        await self._stub.call('REDO')

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

    async def restart_player_pipeline(self, player_id: str) -> None:
        await self._stub.call('RESTART_PLAYER_PIPELINE', self._session_id, player_id)

    async def dump(self) -> None:
        await self._stub.call('DUMP', self._session_id)

    async def render(
            self, callback_address: str, render_settings: render_settings_pb2.RenderSettings
    ) -> None:
        await self._stub.call('RENDER', self._session_id, callback_address, render_settings)

    def add_session_data_listener(
            self, key: str, func: Callable[[Any], None]) -> core.Listener:
        return self.__session_data_listeners.add(key, func)

    async def handle_session_data_mutation(self, data: Dict[str, Any]) -> None:
        for key, value in data.items():
            if key not in self._session_data or self._session_data[key] != value:
                self._session_data[key] = value
                self.__session_data_listeners.call(key, value)

    def set_session_value(self, key: str, value: Any) -> None:
        self.set_session_values({key: value})

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
