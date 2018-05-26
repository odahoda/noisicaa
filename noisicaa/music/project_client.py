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
from typing import (  # pylint: disable=unused-import
    cast, Any, Optional, Dict, Tuple, Callable, Iterable, Iterator, Sequence, Type, TypeVar
)

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
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.listeners = core.CallbackRegistry()

    def property_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyValueChange):
            self.listeners.call(change.prop_name, change.old_value, change.new_value)

        elif isinstance(change, model.PropertyListInsert):
            self.listeners.call(change.prop_name, 'insert', change.index, change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.listeners.call(change.prop_name, 'delete', change.index, change.old_value)

        else:
            raise TypeError("Unsupported change type %s" % type(change))


class ProjectChild(model.ProjectChild, ObjectBase):
    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)


class Track(ProjectChild, model.Track, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def visible(self) -> bool:
        return self.get_property_value('visible')

    @property
    def muted(self) -> bool:
        return self.get_property_value('muted')

    @property
    def gain(self) -> float:
        return self.get_property_value('gain')

    @property
    def pan(self) -> float:
        return self.get_property_value('pan')

    @property
    def mixer_node(self) -> 'BasePipelineGraphNode':
        return self.get_property_value('mixer_node')

    def walk_tracks(self, groups: bool = False, tracks: bool = True) -> Iterator['Track']:
        for track in super().walk_tracks(groups, tracks):
            yield down_cast(Track, track)


class Measure(ProjectChild, model.Measure, ObjectBase):
    pass


class MeasureReference(ProjectChild, model.MeasureReference, ObjectBase):
    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')


class MeasuredTrack(Track, model.MeasuredTrack, ObjectBase):
    # TODO: almost duplicate code. This should be in music/model.py, but only after
    # the UI code has been changed to call the listeners directly with PropertyChange
    # instances.
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = {}  # type: Dict[str, core.Listener]

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.listeners.add('measure_list', self.__measure_list_changed)

    def __measure_list_changed(self, action: str, index: int, value: MeasureReference) -> None:
        if action == 'insert':
            self.__add_measure(value)
        elif action == 'delete':
            self.__remove_measure(value)
        else:
            raise TypeError("Unsupported change type %s" % type(action))

    def __add_measure(self, mref: MeasureReference) -> None:
        self.__listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda *_: self.__measure_id_changed(mref))
        self.listeners.call('duration_changed')

    def __remove_measure(self, mref: MeasureReference) -> None:
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.listeners.call('duration_changed')

    def __measure_id_changed(self, mref: MeasureReference) -> None:
        self.listeners.call('duration_changed')

    @property
    def measure_list(self) -> Sequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def measure_heap(self) -> Sequence[Measure]:
        return self.get_property_value('measure_heap')


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

    def property_changed(self, changes: model.PropertyChange) -> None:
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('notes-changed')


class TrackGroup(Track, model.TrackGroup, ObjectBase):
    # TODO: almost duplicate code. This should be in music/model.py, but only after
    # the UI code has been changed to call the listeners directly with PropertyChange
    # instances.
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = {}  # type: Dict[str, core.Listener]
        for track in self.tracks:
            self.__add_track(track)
        self.listeners.add('tracks', self.__tracks_changed)

    def __tracks_changed(self, action: str, index: int, value: Track) -> None:
        if action == 'insert':
            self.__add_track(value)
        elif action == 'delete':
            self.__remove_track(value)
        else:
            raise TypeError("Unsupported change type %s" % action)

    def __add_track(self, track: Track) -> None:
        self.__listeners['%s:duration_changed' % track.id] = track.listeners.add(
            'duration_changed', lambda: self.listeners.call('duration_changed'))
        self.listeners.call('duration_changed')

    def __remove_track(self, track: Track) -> None:
        self.__listeners.pop('%s:duration_changed' % track.id).remove()
        self.listeners.call('duration_changed')

    @property
    def tracks(self) -> Sequence[Track]:
        return self.get_property_value('tracks')


class MasterTrackGroup(TrackGroup, model.MasterTrackGroup, ObjectBase):
    pass


class ScoreMeasure(Measure, model.ScoreMeasure, ObjectBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.listeners.add('notes', lambda *args: self.listeners.call('notes-changed'))

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
    def instrument(self) -> str:
        return self.get_property_value('instrument')

    @property
    def transpose_octaves(self) -> int:
        return self.get_property_value('transpose_octaves')

    @property
    def instrument_node(self) -> 'InstrumentPipelineGraphNode':
        return self.get_property_value('instrument_node')

    @property
    def event_source_node(self) -> 'PianoRollPipelineGraphNode':
        return self.get_property_value('event_source_node')


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

    def property_changed(self, changes: model.PropertyChange) -> None:
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('beats-changed')


class BeatMeasure(Measure, model.BeatMeasure, ObjectBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.listeners.add('beats', lambda *args: self.listeners.call('beats-changed'))

    @property
    def beats(self) -> Sequence[Beat]:
        return self.get_property_value('beats')


class BeatTrack(MeasuredTrack, model.BeatTrack, ObjectBase):
    @property
    def instrument(self) -> str:
        return self.get_property_value('instrument')

    @property
    def pitch(self) -> model.Pitch:
        return self.get_property_value('pitch')

    @property
    def instrument_node(self) -> 'InstrumentPipelineGraphNode':
        return self.get_property_value('instrument_node')

    @property
    def event_source_node(self) -> 'PianoRollPipelineGraphNode':
        return self.get_property_value('event_source_node')


class PropertyMeasure(Measure, model.PropertyMeasure, ObjectBase):
    @property
    def time_signature(self) -> model.TimeSignature:
        return self.get_property_value('time_signature')


class PropertyTrack(MeasuredTrack, model.PropertyTrack):
    pass


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

    @property
    def generator_node(self) -> 'CVGeneratorPipelineGraphNode':
        return self.get_property_value('generator_node')


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

    @property
    def sample_script_node(self) -> 'SampleScriptPipelineGraphNode':
        return self.get_property_value('sample_script_node')



class PipelineGraphControlValue(ProjectChild, model.PipelineGraphControlValue, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def value(self) -> model.ControlValue:
        return self.get_property_value('value')


class BasePipelineGraphNode(ProjectChild, model.BasePipelineGraphNode, ObjectBase):  # pylint: disable=abstract-method
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def graph_pos(self) -> model.Pos2F:
        return self.get_property_value('graph_pos')

    @property
    def control_values(self) -> Sequence[PipelineGraphControlValue]:
        return self.get_property_value('control_values')

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


class TrackMixerPipelineGraphNode(
        BasePipelineGraphNode, model.TrackMixerPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')


class PianoRollPipelineGraphNode(
        BasePipelineGraphNode, model.PianoRollPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')


class CVGeneratorPipelineGraphNode(
        BasePipelineGraphNode, model.CVGeneratorPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')


class SampleScriptPipelineGraphNode(
        BasePipelineGraphNode, model.SampleScriptPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')


class InstrumentPipelineGraphNode(
        BasePipelineGraphNode, model.InstrumentPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')


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

        self.__duration = audioproc.MusicalDuration()
        self.__master_group_listener = None  # type: core.Listener
        self.listeners.add('master_group', self.__on_master_group_changed)

        # TODO: use correct sample_rate
        self.__time_mapper = audioproc.TimeMapper(44100)
        self.__time_mapper.setup(self)

    def setup(self) -> None:
        super().setup()

        if self.master_group is not None:
            self.__master_group_listener = self.master_group.listeners.add(
                'duration_changed', self.__update_duration)
            self.__update_duration()

    @property
    def master_group(self) -> MasterTrackGroup:
        return self.get_property_value('master_group')

    @property
    def metadata(self) -> Metadata:
        return self.get_property_value('metadata')

    @property
    def property_track(self) -> PropertyTrack:
        return self.get_property_value('property_track')

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
    def all_tracks(self) -> Sequence[Track]:
        return cast(Sequence[Track], super().all_tracks)

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.__duration

    def __update_duration(self) -> None:
        if self.master_group is None:
            return

        new_duration = self.master_group.duration
        if new_duration != self.__duration:
            old_duration = self.__duration
            self.__duration = new_duration
            self.listeners.call('duration', old_duration, new_duration)

    def __on_master_group_changed(
            self, old_value: Optional[MasterTrackGroup], new_value: Optional[MasterTrackGroup]
    ) -> None:
        if self.__master_group_listener is not None:
            self.__master_group_listener.remove()
            self.__master_group_listener = None

        if self.master_group is not None:
            self.__master_group_listener = self.master_group.listeners.add(
                'duration_changed', self.__update_duration)
            self.__update_duration()

    @property
    def time_mapper(self) -> audioproc.TimeMapper:
        return self.__time_mapper

    def init(self, node_db: node_db_lib.NodeDBClient) -> None:
        self.__node_db = node_db

        self.__update_duration()

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.__node_db.get_node_description(uri)


class Pool(model.Pool[ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.register_class(Project)
        self.register_class(TrackGroup)
        self.register_class(MasterTrackGroup)
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
        self.register_class(PropertyMeasure)
        self.register_class(PropertyTrack)
        self.register_class(Metadata)
        self.register_class(Sample)
        self.register_class(Note)
        self.register_class(PipelineGraphConnection)
        self.register_class(PipelineGraphNode)
        self.register_class(InstrumentPipelineGraphNode)
        self.register_class(TrackMixerPipelineGraphNode)
        self.register_class(SampleScriptPipelineGraphNode)
        self.register_class(CVGeneratorPipelineGraphNode)
        self.register_class(PianoRollPipelineGraphNode)
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
        self.listeners = core.CallbackRegistry()

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
