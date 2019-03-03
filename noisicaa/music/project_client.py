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
import random
import socket
from typing import cast, Any, Dict, Tuple, Sequence, Callable, TypeVar

from google.protobuf import message as protobuf

from noisicaa import audioproc
from noisicaa import core
from noisicaa import model
from noisicaa import node_db as node_db_lib
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.builtin_nodes import client_registry
from . import project_process_pb2
from . import mutations as mutations_lib
from . import mutations_pb2
from . import render_settings_pb2
from . import commands_pb2
from . import project_client_model

logger = logging.getLogger(__name__)


def crash() -> commands_pb2.Command:
    return commands_pb2.Command(
        command='crash',
        crash=empty_message_pb2.EmptyMessage())


def update_project(
        *,
        set_bpm: int = None
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='update_project',
        update_project=commands_pb2.UpdateProject(
            set_bpm=set_bpm))


def create_node(
        uri: str,
        *,
        name: str = None,
        graph_pos: model.Pos2F = None,
        graph_size: model.SizeF = None,
        graph_color: model.Color = None,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='create_node',
        create_node=commands_pb2.CreateNode(
            uri=uri,
            name=name,
            graph_pos=graph_pos.to_proto() if graph_pos is not None else None,
            graph_size=graph_size.to_proto() if graph_size is not None else None,
            graph_color=graph_color.to_proto() if graph_color is not None else None))


def update_node(
        node: project_client_model.BaseNode,
        *,
        set_name: str = None,
        set_graph_pos: model.Pos2F = None,
        set_graph_size: model.SizeF = None,
        set_graph_color: model.Color = None,
        set_control_value: model.ControlValue = None,
        set_plugin_state: audioproc.PluginState = None,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='update_node',
        update_node=commands_pb2.UpdateNode(
            node_id=node.id,
            set_name=set_name,
            set_graph_pos=set_graph_pos.to_proto() if set_graph_pos is not None else None,
            set_graph_size=set_graph_size.to_proto() if set_graph_size is not None else None,
            set_graph_color=set_graph_color.to_proto() if set_graph_color is not None else None,
            set_control_value=(
                set_control_value.to_proto() if set_control_value is not None else None),
            set_plugin_state=set_plugin_state))


def delete_node(
        node: project_client_model.BaseNode,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_node',
        delete_node=commands_pb2.DeleteNode(
            node_id=node.id))


def create_node_connection(
        *,
        source_node: project_client_model.BaseNode,
        source_port: str,
        dest_node: project_client_model.BaseNode,
        dest_port: str,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='create_node_connection',
        create_node_connection=commands_pb2.CreateNodeConnection(
            source_node_id=source_node.id,
            source_port_name=source_port,
            dest_node_id=dest_node.id,
            dest_port_name=dest_port))


def delete_node_connection(
        conn: project_client_model.NodeConnection,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_node_connection',
        delete_node_connection=commands_pb2.DeleteNodeConnection(
            connection_id=conn.id))

def update_track(
        track: project_client_model.Track,
        *,
        set_visible: bool = None,
        set_list_position: int = None,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='update_track',
        update_track=commands_pb2.UpdateTrack(
            track_id=track.id,
            set_visible=set_visible,
            set_list_position=set_list_position,
        ))


def create_measure(
        track: project_client_model.MeasuredTrack,
        pos: int,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='create_measure',
        create_measure=commands_pb2.CreateMeasure(
            track_id=track.id,
            pos=pos,
        ))


def update_measure(
        measure: project_client_model.MeasureReference,
        *,
        clear: bool = None,
        set_time_signature: model.TimeSignature = None,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='update_measure',
        update_measure=commands_pb2.UpdateMeasure(
            measure_id=measure.id,
            clear=clear,
            set_time_signature=(
                set_time_signature.to_proto() if set_time_signature is not None else None),
        ))


def delete_measure(
        measure: project_client_model.MeasureReference,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_measure',
        delete_measure=commands_pb2.DeleteMeasure(
            measure_id=measure.id))


def paste_measures(
        mode: str,
        src_objs: Sequence[model.ObjectTree],
        target_ids: Sequence[int],
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='paste_measures',
        paste_measures=commands_pb2.PasteMeasures(
            mode=mode,
            src_objs=src_objs,
            target_ids=target_ids))


class Pool(model.Pool[project_client_model.ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.register_class(project_client_model.Project)
        self.register_class(project_client_model.MeasureReference)
        self.register_class(project_client_model.Metadata)
        self.register_class(project_client_model.Sample)
        self.register_class(project_client_model.NodeConnection)
        self.register_class(project_client_model.Node)
        self.register_class(project_client_model.SystemOutNode)
        client_registry.register_classes(self)


class ProjectClient(object):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            node_db: node_db_lib.NodeDBClient = None) -> None:
        super().__init__()
        self.event_loop = event_loop
        self.__server = server
        self._node_db = node_db

        self._stub = None  # type: ipc.Stub
        self._session_data = None  # type: Dict[str, Any]
        self.__pool = None  # type: Pool
        self.__session_data_listeners = core.CallbackMap[str, Any]()
        self.__closed = None  # type: bool

        self.__cb_endpoint_name = 'project-%016x' % random.getrandbits(63)
        self.__cb_endpoint_address = None  # type: str

    @property
    def project(self) -> project_client_model.Project:
        return cast(project_client_model.Project, self.__pool.root)

    def __set_project(self, root_id: int) -> None:
        project = cast(project_client_model.Project, self.__pool[root_id])
        self.__pool.set_root(project)
        project.init(self._node_db)

    async def setup(self) -> None:
        cb_endpoint = ipc.ServerEndpoint(self.__cb_endpoint_name)
        cb_endpoint.add_handler(
            'PROJECT_MUTATIONS', self.handle_project_mutations,
            mutations_pb2.MutationList, empty_message_pb2.EmptyMessage)
        cb_endpoint.add_handler(
            'PROJECT_CLOSED', self.handle_project_closed,
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        cb_endpoint.add_handler(
            'SESSION_DATA_MUTATION', self.handle_session_data_mutation,
            project_process_pb2.SessionDataMutation, empty_message_pb2.EmptyMessage)

        self.__cb_endpoint_address = await self.__server.add_endpoint(cb_endpoint)

    async def cleanup(self) -> None:
        await self.disconnect()

        if self.__cb_endpoint_address is not None:
            await self.__server.remove_endpoint(self.__cb_endpoint_name)
            self.__cb_endpoint_address = None

    async def connect(self, address: str) -> None:
        assert self._stub is None

        self.__pool = Pool()
        self._session_data = {}
        self.__closed = False

        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect(core.StartSessionRequest(
            callback_address=self.__cb_endpoint_address,
            session_name='%s.%s' % (getpass.getuser(), socket.getfqdn())))

        get_root_id_response = project_process_pb2.ProjectId()
        await self._stub.call('GET_ROOT_ID', None, get_root_id_response)
        if get_root_id_response.HasField('project_id'):
            # Connected to a loaded project.
            self.__set_project(get_root_id_response.project_id)

    async def disconnect(self) -> None:
        if self._stub is not None:
            await self._stub.close()
            self._stub = None

    def get_object(self, obj_id: int) -> project_client_model.ObjectBase:
        return self.__pool[obj_id]

    def handle_project_mutations(
            self,
            request: mutations_pb2.MutationList,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        mutation_list = mutations_lib.MutationList(self.__pool, request)
        mutation_list.apply_forward()

    def handle_project_closed(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        logger.info("Project closed received.")
        self.__closed = True

    async def call(
            self, cmd: str, request: protobuf.Message = None, response: protobuf.Message = None
    ) -> None:
        await self._stub.call(cmd, request, response)

    async def create(self, path: str) -> None:
        request = project_process_pb2.CreateRequest(
            path=path)
        response = project_process_pb2.ProjectId()
        await self._stub.call('CREATE', request, response)
        assert response.HasField('project_id')
        self.__set_project(response.project_id)

    async def create_inmemory(self) -> None:
        response = project_process_pb2.ProjectId()
        await self._stub.call('CREATE_INMEMORY', None, response)
        assert response.HasField('project_id')
        self.__set_project(response.project_id)

    async def open(self, path: str) -> None:
        request = project_process_pb2.OpenRequest(
            path=path)
        response = project_process_pb2.ProjectId()
        await self._stub.call('OPEN', request, response)
        assert response.HasField('project_id')
        self.__set_project(response.project_id)

    async def close(self) -> None:
        assert self.__pool is not None
        await self._stub.call('CLOSE')
        self.__pool = None

    async def send_command(self, command: commands_pb2.Command) -> None:
        assert self.project is not None
        await self.send_command_sequence(
            commands_pb2.CommandSequence(commands=[command]))

    async def send_commands(self, *commands: commands_pb2.Command) -> None:
        await self.send_command_sequence(
            commands_pb2.CommandSequence(commands=commands))

    async def send_command_sequence(self, sequence: commands_pb2.CommandSequence) -> None:
        assert self.project is not None
        try:
            await self._stub.call('COMMAND_SEQUENCE', sequence)
        except ipc.RemoteException:
            if self.__closed:
                raise ipc.ConnectionClosed("Project closed while executing command.")
            raise

    async def undo(self) -> None:
        assert self.project is not None
        await self._stub.call('UNDO')

    async def redo(self) -> None:
        assert self.project is not None
        await self._stub.call('REDO')

    async def create_player(self, *, audioproc_address: str) -> Tuple[str, str]:
        response = project_process_pb2.CreatePlayerResponse()
        await self._stub.call(
            'CREATE_PLAYER',
            project_process_pb2.CreatePlayerRequest(
                client_address=self.__cb_endpoint_address,
                audioproc_address=audioproc_address),
            response)
        return (response.id, response.realm)

    async def delete_player(self, player_id: str) -> None:
        await self._stub.call(
            'DELETE_PLAYER',
            project_process_pb2.DeletePlayerRequest(
                player_id=player_id))

    async def create_plugin_ui(self, player_id: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        response = project_process_pb2.CreatePluginUIResponse()
        await self._stub.call(
            'CREATE_PLUGIN_UI',
            project_process_pb2.CreatePluginUIRequest(
                player_id=player_id,
                node_id=node_id),
            response)
        return (response.wid, (response.width, response.height))

    async def delete_plugin_ui(self, player_id: str, node_id: str) -> None:
        await self._stub.call(
            'DELETE_PLUGIN_UI',
            project_process_pb2.DeletePluginUIRequest(
                player_id=player_id,
                node_id=node_id))

    async def update_player_state(self, player_id: str, state: audioproc.PlayerState) -> None:
        await self._stub.call(
            'UPDATE_PLAYER_STATE',
            project_process_pb2.UpdatePlayerStateRequest(
                player_id=player_id,
                state=state))

    async def dump(self) -> None:
        await self._stub.call('DUMP')

    async def render(
            self, callback_address: str, render_settings: render_settings_pb2.RenderSettings
    ) -> None:
        await self._stub.call(
            'RENDER',
            project_process_pb2.RenderRequest(
                callback_address=callback_address,
                settings=render_settings))

    def add_session_data_listener(
            self, key: str, func: Callable[[Any], None]) -> core.Listener:
        return self.__session_data_listeners.add(key, func)

    async def handle_session_data_mutation(
            self,
            request: project_process_pb2.SessionDataMutation,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        for session_value in request.session_values:
            key = session_value.name
            value = None  # type: Any

            value_type = session_value.WhichOneof('type')
            if value_type == 'string_value':
                value = session_value.string_value
            elif value_type == 'bytes_value':
                value = session_value.bytes_value
            elif value_type == 'bool_value':
                value = session_value.bool_value
            elif value_type == 'int_value':
                value = session_value.int_value
            elif value_type == 'double_value':
                value = session_value.double_value
            elif value_type == 'fraction_value':
                value = Fraction(
                    session_value.fraction_value.numerator,
                    session_value.fraction_value.denominator)
            elif value_type == 'musical_time_value':
                value = audioproc.MusicalTime.from_proto(session_value.musical_time_value)
            elif value_type == 'musical_duration_value':
                value = audioproc.MusicalDuration.from_proto(session_value.musical_time_value)
            else:
                raise ValueError(session_value)

            if key not in self._session_data or self._session_data[key] != value:
                self._session_data[key] = value
                self.__session_data_listeners.call(key, value)

    def set_session_value(self, key: str, value: Any) -> None:
        self.set_session_values({key: value})

    def set_session_values(self, data: Dict[str, Any]) -> None:
        request = project_process_pb2.SetSessionValuesRequest()
        assert isinstance(data, dict), data
        for key, value in data.items():
            session_value = request.session_values.add()
            session_value.name = key
            if isinstance(value, str):
                session_value.string_value = value
            elif isinstance(value, bytes):
                session_value.bytes_value = value
            elif isinstance(value, bool):
                session_value.bool_value = value
            elif isinstance(value, int):
                session_value.int_value = value
            elif isinstance(value, float):
                session_value.double_value = value
            elif isinstance(value, Fraction):
                session_value.fraction_value.numerator = value.numerator
                session_value.fraction_value.denominator = value.denominator
            elif isinstance(value, audioproc.MusicalTime):
                session_value.musical_time_value.numerator = value.numerator
                session_value.musical_time_value.denominator = value.denominator
            elif isinstance(value, audioproc.MusicalDuration):
                session_value.musical_time_value.numerator = value.numerator
                session_value.musical_time_value.denominator = value.denominator
            else:
                raise ValueError("%s: %s" % (key, type(value)))

        self._session_data.update(data)
        self.event_loop.create_task(self._stub.call('SET_SESSION_VALUES', request))

    T = TypeVar('T')
    def get_session_value(self, key: str, default: T) -> T:  # pylint: disable=undefined-variable
        return self._session_data.get(key, default)
