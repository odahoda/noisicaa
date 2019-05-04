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
import functools
import getpass
import logging
import random
import socket
from typing import Any, Dict, List, Tuple, Sequence, Callable, TypeVar

from noisicaa import audioproc
from noisicaa import core
from noisicaa import model_base
from noisicaa import value_types
from noisicaa import lv2
from noisicaa import node_db as node_db_lib
from noisicaa import editor_main_pb2
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.core import session_data_pb2
from . import render_pb2
from . import commands_pb2
from . import project as project_lib
from . import writer_client
from . import render
from . import player as player_lib
from . import session_value_store
from . import graph
from . import base_track

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
        graph_pos: value_types.Pos2F = None,
        graph_size: value_types.SizeF = None,
        graph_color: value_types.Color = None,
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
        node: graph.BaseNode,
        *,
        set_name: str = None,
        set_graph_pos: value_types.Pos2F = None,
        set_graph_size: value_types.SizeF = None,
        set_graph_color: value_types.Color = None,
        set_control_value: value_types.ControlValue = None,
        set_plugin_state: audioproc.PluginState = None,
        set_port_properties: value_types.NodePortProperties = None,
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
            set_plugin_state=set_plugin_state,
            set_port_properties=(
                set_port_properties.to_proto() if set_port_properties is not None else None),
        ))


def delete_node(
        node: graph.BaseNode,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_node',
        delete_node=commands_pb2.DeleteNode(
            node_id=node.id))


def update_port(
        port: graph.Port,
        *,
        set_name: str = None,
        set_display_name: str = None,
        set_type: node_db_lib.PortDescription.Type = None,
        set_direction: node_db_lib.PortDescription.Direction = None,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='update_port',
        update_port=commands_pb2.UpdatePort(
            port_id=port.id,
            set_name=set_name,
            set_display_name=set_display_name,
            set_type=set_type,
            set_direction=set_direction,
        ))


def create_node_connection(
        *,
        source_node: graph.BaseNode,
        source_port: str,
        dest_node: graph.BaseNode,
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
        conn: graph.NodeConnection,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_node_connection',
        delete_node_connection=commands_pb2.DeleteNodeConnection(
            connection_id=conn.id))

def update_track(
        track: base_track.Track,
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
        track: base_track.MeasuredTrack,
        pos: int,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='create_measure',
        create_measure=commands_pb2.CreateMeasure(
            track_id=track.id,
            pos=pos,
        ))


def update_measure(
        measure: base_track.MeasureReference,
        *,
        clear: bool = None,
        set_time_signature: value_types.TimeSignature = None,
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
        measure: base_track.MeasureReference,
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='delete_measure',
        delete_measure=commands_pb2.DeleteMeasure(
            measure_id=measure.id))


def paste_measures(
        mode: str,
        src_objs: Sequence[model_base.ObjectTree],
        target_ids: Sequence[int],
) -> commands_pb2.Command:
    return commands_pb2.Command(
        command='paste_measures',
        paste_measures=commands_pb2.PasteMeasures(
            mode=mode,
            src_objs=src_objs,
            target_ids=target_ids))


class ProjectClient(object):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            manager: ipc.Stub,
            tmp_dir: str,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
    ) -> None:
        self.__event_loop = event_loop
        self.__server = server
        self.__tmp_dir = tmp_dir
        self.__manager = manager

        self.__node_db = node_db
        self.__urid_mapper = urid_mapper
        self.__pool = None  # type: project_lib.Pool
        self.__project = None  # type: project_lib.BaseProject
        self.__writer_client = None  # type: writer_client.WriterClient
        self.__writer_address = None  # type: str
        self.__session_values = None  # type: session_value_store.SessionValueStore
        self.__session_data_listeners = core.CallbackMap[str, Any]()
        self.__players = {}  # type: Dict[str, player_lib.Player]
        self.__cb_endpoint_name = 'project-%016x' % random.getrandbits(63)
        self.__cb_endpoint_address = None  # type: str

    @property
    def project(self) -> project_lib.BaseProject:
        return self.__project

    async def setup(self) -> None:
        cb_endpoint = ipc.ServerEndpoint(self.__cb_endpoint_name)
        cb_endpoint.add_handler(
            'CONTROL_VALUE_CHANGE', self.__handle_control_value_change,
            audioproc.ControlValueChange, empty_message_pb2.EmptyMessage)
        cb_endpoint.add_handler(
            'PLUGIN_STATE_CHANGE', self.__handle_plugin_state_change,
            audioproc.PluginStateChange, empty_message_pb2.EmptyMessage)
        self.__cb_endpoint_address = await self.__server.add_endpoint(cb_endpoint)

    async def cleanup(self) -> None:
        players = list(self.__players.values())
        self.__players.clear()

        for player in players:
            await player.cleanup()

        if self.__cb_endpoint_address is not None:
            await self.__server.remove_endpoint(self.__cb_endpoint_name)
            self.__cb_endpoint_address = None

        await self.close()

    async def __create_writer(self) -> None:
        logger.info("Creating writer process...")
        create_writer_response = editor_main_pb2.CreateProcessResponse()
        await self.__manager.call(
            'CREATE_WRITER_PROCESS', None, create_writer_response)
        self.__writer_address = create_writer_response.address

        logger.info("Connecting to writer process %r...", self.__writer_address)
        self.__writer_client = writer_client.WriterClient(
            event_loop=self.__event_loop)
        await self.__writer_client.setup()
        await self.__writer_client.connect(self.__writer_address)

    async def __init_session_data(self) -> None:
        session_name = '%s.%s' % (getpass.getuser(), socket.getfqdn())
        self.__session_values = session_value_store.SessionValueStore(
            self.__event_loop, session_name)
        await self.__session_values.init(self.__project.data_dir)

        for session_value in self.__session_values.values():
            self.__session_data_listeners.call(
                session_value.name, self.__session_proto_to_py(session_value))

    # def get_object(self, obj_id: int) -> model_base.ObjectBase:
    #     return self.__pool[obj_id]

    async def __handle_control_value_change(
            self,
            request: audioproc.ControlValueChange,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__project is not None

        logger.info(
            "control_value_change(%s, %s, %s, %f, %d)",
            request.realm, request.node_id,
            request.value.name, request.value.value, request.value.generation)

        node = None
        for node in self.__project.nodes:
            if node.pipeline_node_id == request.node_id:
                break

        else:
            raise ValueError("Invalid node_id '%s'" % request.node_id)

        seq = commands_pb2.CommandSequence(
            commands=[commands_pb2.Command(
                command='update_node',
                update_node=commands_pb2.UpdateNode(
                    node_id=node.id,
                    set_control_value=request.value))])

        self.__project.dispatch_command_sequence_proto(seq)

    async def __handle_plugin_state_change(
            self,
            request: audioproc.PluginStateChange,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        assert self.__project is not None

        node = None
        for node in self.__project.nodes:
            if node.pipeline_node_id == request.node_id:
                break
        else:
            raise ValueError("Invalid node_id '%s'" % request.node_id)

        seq = commands_pb2.CommandSequence(
            commands=[commands_pb2.Command(
                command='update_node',
                update_node=commands_pb2.UpdateNode(
                    node_id=node.id,
                    set_plugin_state=request.state))])

        self.__project.dispatch_command_sequence_proto(seq)

    async def create(self, path: str) -> None:
        assert self.__project is None

        await self.__create_writer()

        self.__pool = project_lib.Pool(project_cls=project_lib.Project)
        self.__project = await project_lib.Project.create_blank(
            path=path,
            pool=self.__pool,
            writer=self.__writer_client,
            node_db=self.__node_db)
        await self.__init_session_data()

    async def create_inmemory(self) -> None:
        assert self.__project is None

        self.__pool = project_lib.Pool()
        self.__project = self.__pool.create(
            project_lib.BaseProject, node_db=self.__node_db)
        self.__pool.set_root(self.__project)
        await self.__init_session_data()

    async def open(self, path: str) -> None:
        assert self.__project is None

        await self.__create_writer()

        self.__pool = project_lib.Pool(project_cls=project_lib.Project)
        self.__project = await project_lib.Project.open(
            path=path,
            pool=self.__pool,
            writer=self.__writer_client,
            node_db=self.__node_db)
        await self.__init_session_data()

    async def close(self) -> None:
        if self.__project is not None:
            await self.__project.close()
            self.__project = None
            self.__pool = None

        if self.__writer_client is not None:
            await self.__writer_client.close()
            await self.__writer_client.cleanup()
            self.__writer_client = None

        if self.__writer_address is not None:
            await self.__manager.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.__writer_address))
            self.__writer_address = None

    async def send_command(self, command: commands_pb2.Command) -> None:
        await self.send_command_sequence(
            commands_pb2.CommandSequence(commands=[command]))

    async def send_commands(self, *commands: commands_pb2.Command) -> None:
        await self.send_command_sequence(
            commands_pb2.CommandSequence(commands=commands))

    # TODO: make this sync
    async def send_command_sequence(self, sequence: commands_pb2.CommandSequence) -> None:
        assert self.__project is not None
        self.__project.dispatch_command_sequence_proto(sequence)

    async def undo(self) -> None:
        assert self.__project is not None
        assert isinstance(self.__project, project_lib.Project)

        # TODO: merge fetch_unddo/undo again.
        undo_response = await self.__project.fetch_undo()
        if undo_response is not None:
            action, sequence_data = undo_response
            self.__project.undo(action, sequence_data)

    async def redo(self) -> None:
        assert self.__project is not None
        assert isinstance(self.__project, project_lib.Project)

        # TODO: merge fetch_redo/redo again.
        redo_response = await self.__project.fetch_redo()
        if redo_response is not None:
            action, sequence_data = redo_response
            self.__project.redo(action, sequence_data)

    async def create_player(self, *, audioproc_address: str) -> Tuple[str, str]:
        assert self.__project is not None

        logger.info("Creating audioproc client...")
        audioproc_client = audioproc.AudioProcClient(
            self.__event_loop, self.__server, self.__urid_mapper)
        await audioproc_client.setup()

        logger.info("Connecting audioproc client...")
        await audioproc_client.connect(audioproc_address)

        realm_name = 'project:%s' % self.__project.id
        logger.info("Creating realm '%s'...", realm_name)
        await audioproc_client.create_realm(
            name=realm_name,
            parent='root',
            enable_player=True,
            callback_address=self.__cb_endpoint_address)

        player = player_lib.Player(
            project=self.__project,
            callback_address=self.__cb_endpoint_address,
            event_loop=self.__event_loop,
            audioproc_client=audioproc_client,
            realm=realm_name,
            session_values=self.__session_values)
        await player.setup()

        self.__players[player.id] = player

        return (player.id, player.realm)

    async def delete_player(self, player_id: str) -> None:
        player = self.__players.pop(player_id)
        await player.cleanup()

        if player.audioproc_client is not None:
            if player.realm is not None:
                logger.info("Deleting realm '%s'...", player.realm)
                await player.audioproc_client.delete_realm(name=player.realm)
            await player.audioproc_client.disconnect()
            await player.audioproc_client.cleanup()

    async def create_plugin_ui(self, player_id: str, node_id: str) -> Tuple[int, Tuple[int, int]]:
        player = self.__players[player_id]
        return await player.create_plugin_ui(node_id)

    async def delete_plugin_ui(self, player_id: str, node_id: str) -> None:
        player = self.__players[player_id]
        await player.delete_plugin_ui(node_id)

    async def update_player_state(self, player_id: str, state: audioproc.PlayerState) -> None:
        player = self.__players[player_id]
        await player.update_state(state)

    async def dump(self) -> None:
        raise NotImplementedError
    #     await self._stub.call('DUMP')

    async def render(
            self, callback_address: str, render_settings: render_pb2.RenderSettings
    ) -> None:
        assert self.__project is not None

        renderer = render.Renderer(
            project=self.__project,
            tmp_dir=self.__tmp_dir,
            server=self.__server,
            manager=self.__manager,
            event_loop=self.__event_loop,
            callback_address=callback_address,
            render_settings=render_settings,
            urid_mapper=self.__urid_mapper,
        )
        await renderer.run()

    def add_session_data_listener(
            self, key: str, func: Callable[[Any], None]) -> core.Listener:
        return self.__session_data_listeners.add(key, func)

    def __session_proto_to_py(self, session_value: session_data_pb2.SessionValue) -> Any:
        value_type = session_value.WhichOneof('type')
        if value_type == 'string_value':
            return session_value.string_value
        elif value_type == 'bytes_value':
            return session_value.bytes_value
        elif value_type == 'bool_value':
            return session_value.bool_value
        elif value_type == 'int_value':
            return session_value.int_value
        elif value_type == 'double_value':
            return session_value.double_value
        elif value_type == 'fraction_value':
            return Fraction(
                session_value.fraction_value.numerator,
                session_value.fraction_value.denominator)
        elif value_type == 'musical_time_value':
            return audioproc.MusicalTime.from_proto(session_value.musical_time_value)
        elif value_type == 'musical_duration_value':
            return audioproc.MusicalDuration.from_proto(session_value.musical_time_value)
        else:
            raise ValueError(session_value)

    def set_session_value(self, key: str, value: Any) -> None:
        self.set_session_values({key: value})

    def set_session_values(self, data: Dict[str, Any]) -> None:
        session_values = []  # type: List[session_data_pb2.SessionValue]
        for key, value in data.items():
            session_value = session_data_pb2.SessionValue()
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

        task = self.__event_loop.create_task(self.__session_values.set_values(session_values))
        task.add_done_callback(functools.partial(self.__set_session_values_done, data))

    def __set_session_values_done(self, data: Dict[str, Any], task: asyncio.Task) -> None:
        for key, value in data.items():
            self.__session_data_listeners.call(key, value)

    T = TypeVar('T')
    def get_session_value(self, key: str, default: T) -> T:  # pylint: disable=undefined-variable
        try:
            session_value = self.__session_values.get_value(key)
        except KeyError:
            return default
        else:
            return self.__session_proto_to_py(session_value)
