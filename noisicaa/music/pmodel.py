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

from typing import cast, Any, Iterator, MutableSequence, Sequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import model

# All of these classes are abstract.
# pylint: disable=abstract-method


class ObjectBase(model.ObjectBase):
    _pool = None  # type: Pool

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.listeners = core.CallbackRegistry()

    def property_changed(self, change: model.PropertyChange) -> None:
        self.listeners.call(change.prop_name, change)
        cast(Pool, self._pool).listeners.call('model_changes', self, change)

    def reset_state(self) -> None:
        self.listeners.clear()
        super().reset_state()


class ProjectChild(model.ProjectChild, ObjectBase):
    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)


class TrackConnector(object):
    pass


class Track(ProjectChild, model.Track, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def visible(self) -> bool:
        return self.get_property_value('visible')

    @visible.setter
    def visible(self, value: bool) -> None:
        self.set_property_value('visible', value)

    @property
    def muted(self) -> bool:
        return self.get_property_value('muted')

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_property_value('muted', value)

    @property
    def gain(self) -> float:
        return self.get_property_value('gain')

    @gain.setter
    def gain(self, value: float) -> None:
        self.set_property_value('gain', value)

    @property
    def pan(self) -> float:
        return self.get_property_value('pan')

    @pan.setter
    def pan(self, value: float) -> None:
        self.set_property_value('pan', value)

    @property
    def mixer_node(self) -> 'BasePipelineGraphNode':
        return self.get_property_value('mixer_node')

    @mixer_node.setter
    def mixer_node(self, value: 'BasePipelineGraphNode') -> None:
        self.set_property_value('mixer_node', value)

    @property
    def mixer_name(self) -> str:
        raise NotImplementedError

    @property
    def parent_audio_sink_name(self) -> str:
        raise NotImplementedError

    @property
    def parent_audio_sink_node(self) -> 'BasePipelineGraphNode':
        raise NotImplementedError

    def create_track_connector(self, **kwargs: Any) -> TrackConnector:
        raise NotImplementedError

    def add_pipeline_nodes(self) -> None:
        raise NotImplementedError

    def remove_pipeline_nodes(self) -> None:
        raise NotImplementedError


class Measure(ProjectChild, model.Measure, ObjectBase):
    pass


class MeasureReference(ProjectChild, model.MeasureReference, ObjectBase):
    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')

    @measure.setter
    def measure(self, value: Measure) -> None:
        self.set_property_value('measure', value)


class MeasuredTrack(Track, model.MeasuredTrack, ObjectBase):
    @property
    def measure_list(self) -> MutableSequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def measure_heap(self) -> MutableSequence[Measure]:
        return self.get_property_value('measure_heap')

    def garbage_collect_measures(self) -> None:
        raise NotImplementedError


class Note(ProjectChild, model.Note, ObjectBase):
    @property
    def pitches(self) -> MutableSequence[model.Pitch]:
        return self.get_property_value('pitches')

    @property
    def base_duration(self) -> audioproc.MusicalDuration:
        return self.get_property_value('base_duration')

    @base_duration.setter
    def base_duration(self, value: audioproc.MusicalDuration) -> None:
        self.set_property_value('base_duration', value)

    @property
    def dots(self) -> int:
        return self.get_property_value('dots')

    @dots.setter
    def dots(self, value: int) -> None:
        self.set_property_value('dots', value)

    @property
    def tuplet(self) -> int:
        return self.get_property_value('tuplet')

    @tuplet.setter
    def tuplet(self, value: int) -> None:
        self.set_property_value('tuplet', value)

    @property
    def measure(self) -> 'ScoreMeasure':
        return down_cast(ScoreMeasure, super().measure)


class TrackGroup(Track, model.TrackGroup, ObjectBase):
    @property
    def tracks(self) -> MutableSequence[Track]:
        return self.get_property_value('tracks')


class MasterTrackGroup(TrackGroup, model.MasterTrackGroup, ObjectBase):
    pass


class ScoreMeasure(Measure, model.ScoreMeasure, ObjectBase):
    @property
    def clef(self) -> model.Clef:
        return self.get_property_value('clef')

    @clef.setter
    def clef(self, value: model.Clef) -> None:
        self.set_property_value('clef', value)

    @property
    def key_signature(self) -> model.KeySignature:
        return self.get_property_value('key_signature')

    @key_signature.setter
    def key_signature(self, value: model.KeySignature) -> None:
        self.set_property_value('key_signature', value)

    @property
    def notes(self) -> MutableSequence[Note]:
        return self.get_property_value('notes')

    @property
    def track(self) -> 'ScoreTrack':
        return down_cast(ScoreTrack, super().track)


class ScoreTrack(MeasuredTrack, model.ScoreTrack, ObjectBase):
    @property
    def instrument(self) -> str:
        return self.get_property_value('instrument')

    @instrument.setter
    def instrument(self, value: str) -> None:
        self.set_property_value('instrument', value)

    @property
    def transpose_octaves(self) -> int:
        return self.get_property_value('transpose_octaves')

    @transpose_octaves.setter
    def transpose_octaves(self, value: int) -> None:
        self.set_property_value('transpose_octaves', value)

    @property
    def instrument_node(self) -> 'InstrumentPipelineGraphNode':
        return self.get_property_value('instrument_node')

    @instrument_node.setter
    def instrument_node(self, value: 'InstrumentPipelineGraphNode') -> None:
        self.set_property_value('instrument_node', value)

    @property
    def event_source_node(self) -> 'PianoRollPipelineGraphNode':
        return self.get_property_value('event_source_node')

    @event_source_node.setter
    def event_source_node(self, value: 'PianoRollPipelineGraphNode') -> None:
        self.set_property_value('event_source_node', value)

    @property
    def event_source_name(self) -> str:
        raise NotImplementedError

    @property
    def instr_name(self) -> str:
        raise NotImplementedError


class Beat(ProjectChild, model.Beat, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration.from_proto(self.get_property_value('time'))

    @time.setter
    def time(self, value: audioproc.MusicalDuration) -> None:
        self.set_property_value('time', value.to_proto())

    @property
    def velocity(self) -> int:
        return self.get_property_value('velocity')

    @velocity.setter
    def velocity(self, value: int) -> None:
        self.set_property_value('velocity', value)

    @property
    def measure(self) -> 'BeatMeasure':
        return down_cast(BeatMeasure, super().measure)


class BeatMeasure(Measure, model.BeatMeasure, ObjectBase):
    @property
    def beats(self) -> MutableSequence[Beat]:
        return self.get_property_value('beats')


class BeatTrack(MeasuredTrack, model.BeatTrack, ObjectBase):
    @property
    def instrument(self) -> str:
        return self.get_property_value('instrument')

    @instrument.setter
    def instrument(self, value: str) -> None:
        self.set_property_value('instrument', value)

    @property
    def pitch(self) -> model.Pitch:
        return self.get_property_value('pitch')

    @pitch.setter
    def pitch(self, value: model.Pitch) -> None:
        self.set_property_value('pitch', value)

    @property
    def instrument_node(self) -> 'InstrumentPipelineGraphNode':
        return self.get_property_value('instrument_node')

    @instrument_node.setter
    def instrument_node(self, value: 'InstrumentPipelineGraphNode') -> None:
        self.set_property_value('instrument_node', value)

    @property
    def event_source_node(self) -> 'PianoRollPipelineGraphNode':
        return self.get_property_value('event_source_node')

    @event_source_node.setter
    def event_source_node(self, value: 'PianoRollPipelineGraphNode') -> None:
        self.set_property_value('event_source_node', value)

    @property
    def event_source_name(self) -> str:
        raise NotImplementedError

    @property
    def instr_name(self) -> str:
        raise NotImplementedError


class PropertyMeasure(Measure, model.PropertyMeasure, ObjectBase):
    @property
    def time_signature(self) -> model.TimeSignature:
        return self.get_property_value('time_signature')

    @time_signature.setter
    def time_signature(self, value: model.TimeSignature) -> None:
        self.set_property_value('time_signature', value)


class PropertyTrack(MeasuredTrack, model.PropertyTrack):
    pass


class ControlPoint(ProjectChild, model.ControlPoint, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @time.setter
    def time(self, value: audioproc.MusicalTime) -> None:
        self.set_property_value('time', value)

    @property
    def value(self) -> float:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: float) -> None:
        self.set_property_value('value', value)


class ControlTrack(Track, model.ControlTrack):
    @property
    def points(self) -> MutableSequence[ControlPoint]:
        return self.get_property_value('points')

    @property
    def generator_node(self) -> 'CVGeneratorPipelineGraphNode':
        return self.get_property_value('generator_node')

    @generator_node.setter
    def generator_node(self, value: 'CVGeneratorPipelineGraphNode') -> None:
        self.set_property_value('generator_node', value)

    @property
    def generator_name(self) -> str:
        raise NotImplementedError


class SampleRef(ProjectChild, model.SampleRef, ObjectBase):
    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @time.setter
    def time(self, value: audioproc.MusicalTime) -> None:
        self.set_property_value('time', value)

    @property
    def sample(self) -> 'Sample':
        return self.get_property_value('sample')

    @sample.setter
    def sample(self, value: 'Sample') -> None:
        self.set_property_value('sample', value)


class SampleTrack(Track, model.SampleTrack, ObjectBase):
    @property
    def samples(self) -> MutableSequence[SampleRef]:
        return self.get_property_value('samples')

    @property
    def sample_script_node(self) -> 'SampleScriptPipelineGraphNode':
        return self.get_property_value('sample_script_node')

    @sample_script_node.setter
    def sample_script_node(self, value: 'SampleScriptPipelineGraphNode') -> None:
        self.set_property_value('sample_script_node', value)

    @property
    def sample_script_name(self) -> str:
        raise NotImplementedError



class PipelineGraphControlValue(ProjectChild, model.PipelineGraphControlValue, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def value(self) -> model.ControlValue:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: model.ControlValue) -> None:
        self.set_property_value('value', value)


class BasePipelineGraphNode(ProjectChild, model.BasePipelineGraphNode, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def graph_pos(self) -> model.Pos2F:
        return self.get_property_value('graph_pos')

    @graph_pos.setter
    def graph_pos(self, value: model.Pos2F) -> None:
        self.set_property_value('graph_pos', value)

    @property
    def control_values(self) -> MutableSequence[PipelineGraphControlValue]:
        return self.get_property_value('control_values')

    @property
    def plugin_state(self) -> audioproc.PluginState:
        return self.get_property_value('plugin_state')

    @plugin_state.setter
    def plugin_state(self, value: audioproc.PluginState) -> None:
        self.set_property_value('plugin_state', value)

    @property
    def pipeline_node_id(self) -> str:
        raise NotImplementedError

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def set_control_value(self, port_name: str, value: float, generation: int) -> None:
        raise NotImplementedError

    def set_plugin_state(self, plugin_state: audioproc.PluginState) -> None:
        raise NotImplementedError



class PipelineGraphNode(BasePipelineGraphNode, model.PipelineGraphNode, ObjectBase):
    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @node_uri.setter
    def node_uri(self, value: str) -> None:
        self.set_property_value('node_uri', value)

    def to_preset(self) -> bytes:
        raise NotImplementedError

    def from_preset(self, xml: bytes) -> None:
        raise NotImplementedError


class AudioOutPipelineGraphNode(
        BasePipelineGraphNode, model.AudioOutPipelineGraphNode, ObjectBase):
    pass


class TrackMixerPipelineGraphNode(
        BasePipelineGraphNode, model.TrackMixerPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @track.setter
    def track(self, value: Track) -> None:
        self.set_property_value('track', value)


class PianoRollPipelineGraphNode(
        BasePipelineGraphNode, model.PianoRollPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @track.setter
    def track(self, value: Track) -> None:
        self.set_property_value('track', value)


class CVGeneratorPipelineGraphNode(
        BasePipelineGraphNode, model.CVGeneratorPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @track.setter
    def track(self, value: Track) -> None:
        self.set_property_value('track', value)


class SampleScriptPipelineGraphNode(
        BasePipelineGraphNode, model.SampleScriptPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @track.setter
    def track(self, value: Track) -> None:
        self.set_property_value('track', value)


class InstrumentPipelineGraphNode(
        BasePipelineGraphNode, model.InstrumentPipelineGraphNode, ObjectBase):
    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @track.setter
    def track(self, value: Track) -> None:
        self.set_property_value('track', value)

    def get_update_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError


class PipelineGraphConnection(ProjectChild, model.PipelineGraphConnection, ObjectBase):
    @property
    def source_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('source_node')

    @source_node.setter
    def source_node(self, value: BasePipelineGraphNode) -> None:
        self.set_property_value('source_node', value)

    @property
    def source_port(self) -> str:
        return self.get_property_value('source_port')

    @source_port.setter
    def source_port(self, value: str) -> None:
        self.set_property_value('source_port', value)

    @property
    def dest_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('dest_node')

    @dest_node.setter
    def dest_node(self, value: BasePipelineGraphNode) -> None:
        self.set_property_value('dest_node', value)

    @property
    def dest_port(self) -> str:
        return self.get_property_value('dest_port')

    @dest_port.setter
    def dest_port(self, value: str) -> None:
        self.set_property_value('dest_port', value)

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError


class Sample(ProjectChild, model.Sample, ObjectBase):
    @property
    def path(self) -> str:
        return self.get_property_value('path')

    @path.setter
    def path(self, value: str) -> None:
        self.set_property_value('path', value)


class Metadata(ProjectChild, model.Metadata, ObjectBase):
    @property
    def author(self) -> str:
        return self.get_property_value('author')

    @author.setter
    def author(self, value: str) -> None:
        self.set_property_value('author', value)

    @property
    def license(self) -> str:
        return self.get_property_value('license')

    @license.setter
    def license(self, value: str) -> None:
        self.set_property_value('license', value)

    @property
    def copyright(self) -> str:
        return self.get_property_value('copyright')

    @copyright.setter
    def copyright(self, value: str) -> None:
        self.set_property_value('copyright', value)

    @property
    def created(self) -> int:
        return self.get_property_value('created')

    @created.setter
    def created(self, value: int) -> None:
        self.set_property_value('created', value)


class Project(model.Project, ObjectBase):
    @property
    def master_group(self) -> MasterTrackGroup:
        return self.get_property_value('master_group')

    @master_group.setter
    def master_group(self, value: MasterTrackGroup) -> None:
        self.set_property_value('master_group', value)

    @property
    def metadata(self) -> Metadata:
        return self.get_property_value('metadata')

    @metadata.setter
    def metadata(self, value: Metadata) -> None:
        self.set_property_value('metadata', value)

    @property
    def property_track(self) -> PropertyTrack:
        return self.get_property_value('property_track')

    @property_track.setter
    def property_track(self, value: PropertyTrack) -> None:
        self.set_property_value('property_track', value)

    @property
    def pipeline_graph_nodes(self) -> MutableSequence[BasePipelineGraphNode]:
        return self.get_property_value('pipeline_graph_nodes')

    @property
    def pipeline_graph_connections(self) -> MutableSequence[PipelineGraphConnection]:
        return self.get_property_value('pipeline_graph_connections')

    @property
    def samples(self) -> MutableSequence[Sample]:
        return self.get_property_value('samples')

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @bpm.setter
    def bpm(self, value: int) -> None:
        self.set_property_value('bpm', value)

    @property
    def all_tracks(self) -> Sequence[Track]:
        return cast(Sequence[Track], super().all_tracks)

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    def add_track(self, parent_group: TrackGroup, insert_index: int, track: Track) -> None:
        raise NotImplementedError  # pragma: no coverage

    def remove_track(self, parent_group: TrackGroup, track: Track) -> None:
        raise NotImplementedError  # pragma: no coverage

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        raise NotImplementedError  # pragma: no coverage

    @property
    def audio_out_node(self) -> BasePipelineGraphNode:
        raise NotImplementedError  # pragma: no coverage

    def add_pipeline_graph_node(self, node: BasePipelineGraphNode) -> None:
        raise NotImplementedError  # pragma: no coverage

    def remove_pipeline_graph_node(self, node: BasePipelineGraphNode) -> None:
        raise NotImplementedError  # pragma: no coverage

    def add_pipeline_graph_connection(self, connection: PipelineGraphConnection) -> None:
        raise NotImplementedError  # pragma: no coverage

    def remove_pipeline_graph_connection(self, connection: PipelineGraphConnection) -> None:
        raise NotImplementedError  # pragma: no coverage

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError  # pragma: no coverage

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError  # pragma: no coverage


class Pool(model.Pool[ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.listeners = core.CallbackRegistry()

    def object_added(self, obj: model.ObjectBase) -> None:
        self.listeners.call('model_changes', obj, model.ObjectAdded(obj))

    def object_removed(self, obj: model.ObjectBase) -> None:
        self.listeners.call('model_changes', obj, model.ObjectRemoved(obj))
