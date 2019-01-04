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
from typing import cast, Any, Dict, Tuple, Callable, Sequence, TypeVar

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import model
from noisicaa import node_db as node_db_lib
from noisicaa.core import ipc
from . import mutations as mutations_lib
from . import mutations_pb2
from . import render_settings_pb2
from . import commands_pb2

logger = logging.getLogger(__name__)


class ObjectBase(model.ObjectBase):  # pylint: disable=abstract-method
    pass


class ProjectChild(model.ProjectChild, ObjectBase):
    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)


class PipelineGraphControlValue(ProjectChild, model.PipelineGraphControlValue, ObjectBase):
    pass


class BasePipelineGraphNode(ProjectChild, model.BasePipelineGraphNode, ObjectBase):  # pylint: disable=abstract-method
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def graph_pos(self) -> model.Pos2F:
        return self.get_property_value('graph_pos')

    @property
    def graph_size(self) -> model.SizeF:
        return self.get_property_value('graph_size')

    @property
    def graph_color(self) -> model.Color:
        return self.get_property_value('graph_color')

    @property
    def plugin_state(self) -> audioproc.PluginState:
        return self.get_property_value('plugin_state')



class PipelineGraphNode(BasePipelineGraphNode, model.PipelineGraphNode, ObjectBase):
    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')


class AudioOutPipelineGraphNode(
        BasePipelineGraphNode, model.AudioOutPipelineGraphNode, ObjectBase):
    pass


class Track(BasePipelineGraphNode, model.Track, ObjectBase):  # pylint: disable=abstract-method
    @property
    def visible(self) -> bool:
        return self.get_property_value('visible')

    @property
    def list_position(self) -> int:
        return self.get_property_value('list_position')


class Measure(ProjectChild, model.Measure, ObjectBase):
    @property
    def time_signature(self) -> model.TimeSignature:
        return self.get_property_value('time_signature')


class MeasureReference(ProjectChild, model.MeasureReference, ObjectBase):
    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')


class MeasuredTrack(Track, model.MeasuredTrack, ObjectBase):  # pylint: disable=abstract-method
    @property
    def measure_list(self) -> Sequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def measure_heap(self) -> Sequence[Measure]:
        return self.get_property_value('measure_heap')


class ControlPoint(ProjectChild, model.ControlPoint, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @property
    def value(self) -> float:
        return self.get_property_value('value')


class ControlTrack(Track, model.ControlTrack):
    @property
    def points(self) -> Sequence[ControlPoint]:
        return self.get_property_value('points')


class Note(ProjectChild, model.Note, ObjectBase):
    @property
    def pitches(self) -> Sequence[model.Pitch]:
        return self.get_property_value('pitches')

    @property
    def base_duration(self) -> audioproc.MusicalDuration:
        return self.get_property_value('base_duration')

    @property
    def dots(self) -> int:
        return self.get_property_value('dots')

    @property
    def tuplet(self) -> int:
        return self.get_property_value('tuplet')

    @property
    def measure(self) -> 'ScoreMeasure':
        return down_cast(ScoreMeasure, super().measure)


class ScoreMeasure(Measure, model.ScoreMeasure, ObjectBase):
    @property
    def clef(self) -> model.Clef:
        return self.get_property_value('clef')

    @property
    def key_signature(self) -> model.KeySignature:
        return self.get_property_value('key_signature')

    @property
    def notes(self) -> Sequence[Note]:
        return self.get_property_value('notes')

    @property
    def track(self) -> 'ScoreTrack':
        return down_cast(ScoreTrack, super().track)


class ScoreTrack(MeasuredTrack, model.ScoreTrack, ObjectBase):
    @property
    def transpose_octaves(self) -> int:
        return self.get_property_value('transpose_octaves')


class Beat(ProjectChild, model.Beat, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration.from_proto(self.get_property_value('time'))

    @property
    def velocity(self) -> int:
        return self.get_property_value('velocity')

    @property
    def measure(self) -> 'BeatMeasure':
        return down_cast(BeatMeasure, super().measure)


class BeatMeasure(Measure, model.BeatMeasure, ObjectBase):
    @property
    def beats(self) -> Sequence[Beat]:
        return self.get_property_value('beats')


class BeatTrack(MeasuredTrack, model.BeatTrack, ObjectBase):
    @property
    def pitch(self) -> model.Pitch:
        return self.get_property_value('pitch')


class SampleRef(ProjectChild, model.SampleRef, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @property
    def sample(self) -> 'Sample':
        return self.get_property_value('sample')


class SampleTrack(Track, model.SampleTrack, ObjectBase):
    @property
    def samples(self) -> Sequence[SampleRef]:
        return self.get_property_value('samples')


class Instrument(BasePipelineGraphNode, model.Instrument, ObjectBase):
    @property
    def instrument_uri(self) -> str:
        return self.get_property_value('instrument_uri')


class PipelineGraphConnection(ProjectChild, model.PipelineGraphConnection, ObjectBase):
    @property
    def source_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('source_node')

    @property
    def source_port(self) -> str:
        return self.get_property_value('source_port')

    @property
    def dest_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('dest_node')

    @property
    def dest_port(self) -> str:
        return self.get_property_value('dest_port')


class Sample(ProjectChild, model.Sample, ObjectBase):
    @property
    def path(self) -> str:
        return self.get_property_value('path')


class Metadata(ProjectChild, model.Metadata, ObjectBase):
    @property
    def author(self) -> str:
        return self.get_property_value('author')

    @property
    def license(self) -> str:
        return self.get_property_value('license')

    @property
    def copyright(self) -> str:
        return self.get_property_value('copyright')

    @property
    def created(self) -> int:
        return self.get_property_value('created')


class Project(model.Project, ObjectBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_db = None  # type: node_db_lib.NodeDBClient
        self.__time_mapper = None  # type: audioproc.TimeMapper

    @property
    def metadata(self) -> Metadata:
        return self.get_property_value('metadata')

    @property
    def pipeline_graph_nodes(self) -> Sequence[BasePipelineGraphNode]:
        return self.get_property_value('pipeline_graph_nodes')

    @property
    def pipeline_graph_connections(self) -> Sequence[PipelineGraphConnection]:
        return self.get_property_value('pipeline_graph_connections')

    @property
    def samples(self) -> Sequence[Sample]:
        return self.get_property_value('samples')

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    @property
    def time_mapper(self) -> audioproc.TimeMapper:
        return self.__time_mapper

    def init(self, node_db: node_db_lib.NodeDBClient) -> None:
        self.__node_db = node_db

        # TODO: use correct sample_rate
        self.__time_mapper = audioproc.TimeMapper(44100)
        self.__time_mapper.setup(self)

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.__node_db.get_node_description(uri)


class Pool(model.Pool[ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.register_class(Project)
        self.register_class(MeasureReference)
        self.register_class(ScoreMeasure)
        self.register_class(ScoreTrack)
        self.register_class(Beat)
        self.register_class(BeatMeasure)
        self.register_class(BeatTrack)
        self.register_class(SampleRef)
        self.register_class(SampleTrack)
        self.register_class(ControlPoint)
        self.register_class(ControlTrack)
        self.register_class(Metadata)
        self.register_class(Sample)
        self.register_class(Note)
        self.register_class(PipelineGraphConnection)
        self.register_class(PipelineGraphNode)
        self.register_class(Instrument)
        self.register_class(AudioOutPipelineGraphNode)
        self.register_class(PipelineGraphControlValue)


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
        self.project = None  # type: Project
        self.__session_data_listeners = core.CallbackMap[str, Any]()

    def __set_project(self, root_id: int) -> None:
        assert self.project is None
        self.project = cast(Project, self.__pool[root_id])
        self.project.init(self._node_db)

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

    def get_object(self, obj_id: int) -> ObjectBase:
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
        self.__pool = None

    async def send_command(self, command: commands_pb2.Command) -> Any:
        assert self.project is not None
        result = await self._stub.call('COMMAND', command)
        logger.info("Command %s completed with result=%r", command.WhichOneof('command'), result)
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
