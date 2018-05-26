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

import fractions
from typing import cast, Any, Iterator, Sequence, List, Union  # pylint: disable=unused-import

from google.protobuf import message as protobuf  # pylint: disable=unused-import

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import instrument_db
from noisicaa.audioproc.public import musical_time_pb2
from . import pitch as pitch_lib
from . import clef as clef_lib
from . import key_signature as key_signature_lib
from . import time_signature as time_signature_lib
from . import pos2f
from . import model_base
from . import project_pb2


class ObjectBase(model_base.ObjectBase):
    @property
    def parent(self) -> 'ObjectBase':
        return cast(ObjectBase, super().parent)

    @property
    def project(self) -> 'Project':
        raise NotImplementedError

    @property
    def attached_to_project(self) -> bool:
        raise NotImplementedError


class ProjectChild(ObjectBase):
    @property
    def project(self) -> 'Project':
        assert self.is_attached
        return cast(Union[ProjectChild, Project], self.parent).project

    @property
    def attached_to_project(self) -> bool:
        if not self.is_attached:
            return None
        return self.parent.attached_to_project


class Sample(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'sample'
        proto_ext = project_pb2.sample  # type: ignore

        path = model_base.Property(str)


class PipelineGraphControlValue(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_control_value'
        proto_ext = project_pb2.pipeline_graph_control_value  # type: ignore

        name = model_base.Property(str)
        value = model_base.ProtoProperty(project_pb2.ControlValue)


class BasePipelineGraphNode(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_ext = project_pb2.base_pipeline_graph_node  # type: ignore

        name = model_base.Property(str)
        graph_pos = model_base.WrappedProtoProperty(pos2f.Pos2F)
        control_values = model_base.ObjectListProperty(PipelineGraphControlValue)
        plugin_state = model_base.ProtoProperty(audioproc.PluginState, allow_none=True)

    @property
    def removable(self) -> bool:
        raise NotImplementedError

    @property
    def description(self) -> node_db.NodeDescription:
        raise NotImplementedError


class Track(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_ext = project_pb2.track  # type: ignore

        name = model_base.Property(str)
        visible = model_base.Property(bool, default=True)
        muted = model_base.Property(bool, default=False)
        gain = model_base.Property(float, default=0.0)
        pan = model_base.Property(float, default=0.0)
        mixer_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode, allow_none=True)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1, 1)

    @property
    def is_master_group(self) -> bool:
        return False

    def walk_tracks(self, groups: bool = False, tracks: bool = True) -> Iterator['Track']:
        if tracks:
            yield self


class Measure(ProjectChild):
    @property
    def track(self) -> Track:
        return cast(Track, self.parent)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        time_signature = self.project.get_time_signature(self.index)
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)


class MeasureReference(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'measure_reference'
        proto_ext = project_pb2.measure_reference  # type: ignore

        measure = model_base.ObjectReferenceProperty(Measure)

    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')

    @property
    def track(self) -> Track:
        return cast(Track, self.parent)

    @property
    def prev_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().prev_sibling)

    @property
    def next_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().next_sibling)


class MeasuredTrack(Track):
    class Spec(model_base.ObjectSpec):
        proto_ext = project_pb2.measured_track  # type: ignore

        measure_list = model_base.ObjectListProperty(MeasureReference)
        measure_heap = model_base.ObjectListProperty(Measure)

    @property
    def measure_list(self) -> Sequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = audioproc.MusicalDuration()
        for mref in self.measure_list:
            duration += mref.measure.duration
        return duration


class Note(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'note'
        proto_ext = project_pb2.note  # type: ignore

        pitches = model_base.WrappedProtoListProperty(pitch_lib.Pitch)
        base_duration = model_base.WrappedProtoProperty(
            audioproc.MusicalDuration,
            default=audioproc.MusicalDuration(1, 4))
        dots = model_base.Property(int, default=0)
        tuplet = model_base.Property(int, default=0)

    @property
    def pitches(self) -> Sequence[pitch_lib.Pitch]:
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
        return cast(ScoreMeasure, self.parent)

    @property
    def is_rest(self) -> bool:
        pitches = self.pitches
        return len(pitches) == 1 and pitches[0].is_rest

    @property
    def max_allowed_dots(self) -> int:
        base_duration = self.base_duration
        if base_duration <= audioproc.MusicalDuration(1, 32):
            return 0
        if base_duration <= audioproc.MusicalDuration(1, 16):
            return 1
        if base_duration <= audioproc.MusicalDuration(1, 8):
            return 2
        return 3

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = self.base_duration
        dots = self.dots
        tuplet = self.tuplet
        for _ in range(dots):
            duration *= fractions.Fraction(3, 2)
        if tuplet == 3:
            duration *= fractions.Fraction(2, 3)
        elif tuplet == 5:
            duration *= fractions.Fraction(4, 5)
        return audioproc.MusicalDuration(duration)


class TrackGroup(Track):
    class Spec(model_base.ObjectSpec):
        proto_type = 'track_group'
        proto_ext = project_pb2.track_group  # type: ignore

        tracks = model_base.ObjectListProperty(Track)

    @property
    def tracks(self) -> Sequence[Track]:
        return self.get_property_value('tracks')

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = audioproc.MusicalDuration()
        for track in self.tracks:
            duration = max(duration, track.duration)
        return duration

    def walk_tracks(self, groups: bool = False, tracks: bool = True) -> Iterator[Track]:
        if groups:
            yield self

        for track in self.tracks:
            yield from track.walk_tracks(groups, tracks)


class MasterTrackGroup(TrackGroup):
    class Spec(model_base.ObjectSpec):
        proto_type = 'master_track_group'

    @property
    def is_master_group(self) -> bool:
        return True


class PropertyMeasure(Measure):
    class Spec(model_base.ObjectSpec):
        proto_type = 'property_measure'
        proto_ext = project_pb2.property_measure  # type: ignore

        time_signature = model_base.WrappedProtoProperty(
            time_signature_lib.TimeSignature,
            default=time_signature_lib.TimeSignature(4, 4))

    @property
    def time_signature(self) -> time_signature_lib.TimeSignature:
        return self.get_property_value('time_signature')


class PropertyTrack(MeasuredTrack):
    class Spec(model_base.ObjectSpec):
        proto_type = 'property_track'


class PipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_node'
        proto_ext = project_pb2.pipeline_graph_node  # type: ignore

        node_uri = model_base.Property(str)

    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @property
    def removable(self) -> bool:
        return True

    @property
    def description(self) -> node_db.NodeDescription:
        return self.project.get_node_description(self.node_uri)


class AudioOutPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'audio_out_pipeline_graph_node'

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.RealmSinkDescription


class TrackMixerPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'track_mixer_pipeline_graph_node'
        proto_ext = project_pb2.track_mixer_pipeline_graph_node  # type: ignore

        track = model_base.ObjectReferenceProperty(Track)

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.TrackMixerDescription


class InstrumentPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'instrument_pipeline_graph_node'
        proto_ext = project_pb2.instrument_pipeline_graph_node  # type: ignore

        track = model_base.ObjectReferenceProperty(Track)

    @property
    def track(self) -> Track:
        return self.get_property_value('track')

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return instrument_db.parse_uri(
            cast(Union[ScoreTrack, BeatTrack], self.track).instrument,
            self.project.get_node_description)


class PianoRollPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'pianoroll_pipeline_graph_node'
        proto_ext = project_pb2.pianoroll_pipeline_graph_node  # type: ignore

        track = model_base.ObjectReferenceProperty(Track)

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.PianoRollDescription


class ScoreMeasure(Measure):
    class Spec(model_base.ObjectSpec):
        proto_type = 'score_measure'
        proto_ext = project_pb2.score_measure  # type: ignore

        clef = model_base.WrappedProtoProperty(clef_lib.Clef, default=clef_lib.Clef.Treble)
        key_signature = model_base.WrappedProtoProperty(
            key_signature_lib.KeySignature,
            default=key_signature_lib.KeySignature('C major'))
        notes = model_base.ObjectListProperty(Note)

    @property
    def time_signature(self) -> time_signature_lib.TimeSignature:
        return self.project.get_time_signature(self.index)


class ScoreTrack(MeasuredTrack):
    class Spec(model_base.ObjectSpec):
        proto_type = 'score_track'
        proto_ext = project_pb2.score_track  # type: ignore

        instrument = model_base.Property(str)
        transpose_octaves = model_base.Property(int, default=0)
        instrument_node = model_base.ObjectReferenceProperty(
            InstrumentPipelineGraphNode, allow_none=True)
        event_source_node = model_base.ObjectReferenceProperty(
            PianoRollPipelineGraphNode, allow_none=True)

    @property
    def instrument(self) -> str:
        return self.get_property_value('instrument')


class Beat(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'beat'
        proto_ext = project_pb2.beat  # type: ignore

        time = model_base.ProtoProperty(musical_time_pb2.MusicalDuration)
        velocity = model_base.Property(int)

    @property
    def measure(self) -> 'BeatMeasure':
        return cast(BeatMeasure, self.parent)


class BeatMeasure(Measure):
    class Spec(model_base.ObjectSpec):
        proto_type = 'beat_measure'
        proto_ext = project_pb2.beat_measure  # type: ignore

        beats = model_base.ObjectListProperty(Beat)

    @property
    def time_signature(self) -> time_signature_lib.TimeSignature:
        return self.project.get_time_signature(self.index)


class BeatTrack(MeasuredTrack):
    class Spec(model_base.ObjectSpec):
        proto_type = 'beat_track'
        proto_ext = project_pb2.beat_track  # type: ignore

        instrument = model_base.Property(str)
        pitch = model_base.WrappedProtoProperty(pitch_lib.Pitch)
        instrument_node = model_base.ObjectReferenceProperty(
            InstrumentPipelineGraphNode, allow_none=True)
        event_source_node = model_base.ObjectReferenceProperty(
            PianoRollPipelineGraphNode, allow_none=True)

    @property
    def instrument(self) -> str:
        return self.get_property_value('instrument')


class CVGeneratorPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'cvgenerator_pipeline_graph_node'
        proto_ext = project_pb2.cvgenerator_pipeline_graph_node  # type: ignore

        track = model_base.ObjectReferenceProperty(Track)

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.CVGeneratorDescription


class ControlPoint(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'control_point'
        proto_ext = project_pb2.control_point  # type: ignore

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        value = model_base.Property(float)


class ControlTrack(Track):
    class Spec(model_base.ObjectSpec):
        proto_type = 'control_track'
        proto_ext = project_pb2.control_track  # type: ignore

        points = model_base.ObjectListProperty(ControlPoint)
        generator_node = model_base.ObjectReferenceProperty(
            CVGeneratorPipelineGraphNode, allow_none=True)


class SampleScriptPipelineGraphNode(BasePipelineGraphNode):
    class Spec(model_base.ObjectSpec):
        proto_type = 'sample_script_pipeline_graph_node'
        proto_ext = project_pb2.sample_script_pipeline_graph_node  # type: ignore

        track = model_base.ObjectReferenceProperty(Track)

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.SampleScriptDescription


class SampleRef(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'sample_ref'
        proto_ext = project_pb2.sample_ref  # type: ignore

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        sample = model_base.ObjectReferenceProperty(Sample)


class SampleTrack(Track):
    class Spec(model_base.ObjectSpec):
        proto_type = 'sample_track'
        proto_ext = project_pb2.sample_track  # type: ignore

        samples = model_base.ObjectListProperty(SampleRef)
        sample_script_node = model_base.ObjectReferenceProperty(
            SampleScriptPipelineGraphNode, allow_none=True)


class PipelineGraphConnection(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_connection'
        proto_ext = project_pb2.pipeline_graph_connection  # type: ignore

        source_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        source_port = model_base.Property(str)
        dest_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        dest_port = model_base.Property(str)


class Metadata(ProjectChild):
    class Spec(model_base.ObjectSpec):
        proto_type = 'metadata'
        proto_ext = project_pb2.metadata  # type: ignore

        author = model_base.Property(str, allow_none=True)
        license = model_base.Property(str, allow_none=True)
        copyright = model_base.Property(str, allow_none=True)
        created = model_base.Property(int, allow_none=True)


class Project(ObjectBase):
    class Spec(model_base.ObjectSpec):
        proto_type = 'project'
        proto_ext = project_pb2.project  # type: ignore

        metadata = model_base.ObjectProperty(Metadata)
        master_group = model_base.ObjectProperty(MasterTrackGroup)
        property_track = model_base.ObjectProperty(PropertyTrack)
        pipeline_graph_nodes = model_base.ObjectListProperty(BasePipelineGraphNode)
        pipeline_graph_connections = model_base.ObjectListProperty(PipelineGraphConnection)
        samples = model_base.ObjectListProperty(Sample)
        bpm = model_base.Property(int, default=120)

    @property
    def master_group(self) -> MasterTrackGroup:
        return self.get_property_value('master_group')

    @property
    def property_track(self) -> PropertyTrack:
        return self.get_property_value('property_track')

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @property
    def project(self) -> 'Project':
        return self

    @property
    def attached_to_project(self) -> bool:
        return True

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.master_group.duration

    @property
    def all_tracks(self) -> Sequence[Track]:
        tracks = []  # type: List[Track]
        tracks.append(self.property_track)
        tracks.extend(self.master_group.walk_tracks())
        return tracks

    def get_bpm(self, measure_idx: int, tick: int) -> int:  # pylint: disable=unused-argument
        return self.bpm

    def get_time_signature(self, measure_idx: int) -> time_signature_lib.TimeSignature:
        # TODO: this is called with an incorrect measure_idx (index of the measure within the
        #   measure_heap), so always use the time signature from the first measure, which
        #   is also wrong, but at least doesn't crash.
        return cast(PropertyMeasure, self.property_track.measure_list[0].measure).time_signature


    def get_node_description(self, uri: str) -> node_db.NodeDescription:
        raise NotImplementedError
