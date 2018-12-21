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
import logging
from typing import cast, Any, Dict, Set, Iterator, Sequence, List, Union  # pylint: disable=unused-import

from google.protobuf import message as protobuf  # pylint: disable=unused-import

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import instrument_db
from noisicaa.audioproc.public import musical_time_pb2
from . import pitch as pitch_lib
from . import clef as clef_lib
from . import key_signature as key_signature_lib
from . import time_signature as time_signature_lib
from . import pos2f
from . import sizef
from . import color
from . import model_base
from . import project_pb2

logger = logging.getLogger(__name__)


class ObjectBase(model_base.ObjectBase):
    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        callback = getattr(self, change.prop_name + '_changed')
        callback.call(change)

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
    class SampleSpec(model_base.ObjectSpec):
        proto_type = 'sample'
        proto_ext = project_pb2.sample  # type: ignore

        path = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.path_changed = core.Callback[model_base.PropertyChange[str]]()


class PipelineGraphControlValue(ProjectChild):
    class PipelineGraphControlValueSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_control_value'
        proto_ext = project_pb2.pipeline_graph_control_value  # type: ignore

        name = model_base.Property(str)
        value = model_base.ProtoProperty(project_pb2.ControlValue)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.value_changed = core.Callback[model_base.PropertyChange[project_pb2.ControlValue]]()


class BasePipelineGraphNode(ProjectChild):
    class BasePipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.base_pipeline_graph_node  # type: ignore

        name = model_base.Property(str)
        graph_pos = model_base.WrappedProtoProperty(pos2f.Pos2F)
        graph_size = model_base.WrappedProtoProperty(sizef.SizeF)
        graph_color = model_base.WrappedProtoProperty(
            color.Color, default=color.Color(0.8, 0.8, 0.8, 1.0))
        control_values = model_base.ObjectListProperty(PipelineGraphControlValue)
        plugin_state = model_base.ProtoProperty(audioproc.PluginState, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.graph_pos_changed = core.Callback[model_base.PropertyChange[pos2f.Pos2F]]()
        self.graph_size_changed = core.Callback[model_base.PropertyChange[sizef.SizeF]]()
        self.graph_color_changed = core.Callback[model_base.PropertyChange[color.Color]]()
        self.control_values_changed = \
            core.Callback[model_base.PropertyListChange[PipelineGraphControlValue]]()
        self.plugin_state_changed = \
            core.Callback[model_base.PropertyChange[audioproc.PluginState]]()

    @property
    def removable(self) -> bool:
        return True

    @property
    def description(self) -> node_db.NodeDescription:
        raise NotImplementedError

    def upstream_nodes(self) -> List['BasePipelineGraphNode']:
        node_ids = set()  # type: Set[int]
        self.__upstream_nodes(node_ids)
        return [self._pool[node_id] for node_id in sorted(node_ids)]

    def __upstream_nodes(self, seen: Set[int]) -> None:
        for connection in self.project.get_property_value('pipeline_graph_connections'):
            if connection.dest_node is self and connection.source_node.id not in seen:
                seen.add(connection.source_node.id)
                connection.source_node.__upstream_nodes(seen)


class PipelineGraphConnection(ProjectChild):
    class PipelineGraphConnectionSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_connection'
        proto_ext = project_pb2.pipeline_graph_connection  # type: ignore

        source_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        source_port = model_base.Property(str)
        dest_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        dest_port = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.source_node_changed = core.Callback[model_base.PropertyChange[BasePipelineGraphNode]]()
        self.source_port_changed = core.Callback[model_base.PropertyChange[str]]()
        self.dest_node_changed = core.Callback[model_base.PropertyChange[BasePipelineGraphNode]]()
        self.dest_port_changed = core.Callback[model_base.PropertyChange[str]]()


class PipelineGraphNode(BasePipelineGraphNode):
    class PipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_node'
        proto_ext = project_pb2.pipeline_graph_node  # type: ignore

        node_uri = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.node_uri_changed = core.Callback[model_base.PropertyChange[str]]()

    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @property
    def description(self) -> node_db.NodeDescription:
        return self.project.get_node_description(self.node_uri)


class AudioOutPipelineGraphNode(BasePipelineGraphNode):
    class AudioOutPipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_type = 'audio_out_pipeline_graph_node'

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.RealmSinkDescription


class InstrumentPipelineGraphNode(BasePipelineGraphNode):
    class InstrumentPipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_type = 'instrument_pipeline_graph_node'
        proto_ext = project_pb2.instrument_pipeline_graph_node  # type: ignore

        instrument_uri = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.instrument_uri_changed = core.Callback[model_base.PropertyChange[str]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return instrument_db.parse_uri(
            self.get_property_value('instrument_uri'), self.project.get_node_description)


class Track(BasePipelineGraphNode):  # pylint: disable=abstract-method
    class TrackSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.track  # type: ignore

        visible = model_base.Property(bool, default=True)
        list_position = model_base.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.visible_changed = core.Callback[model_base.PropertyChange[bool]]()
        self.list_position_changed = core.Callback[model_base.PropertyChange[int]]()
        self.duration_changed = core.Callback[None]()

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1, 1)


class Measure(ProjectChild):
    class MeasureSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.measure  # type: ignore

        time_signature = model_base.WrappedProtoProperty(
            time_signature_lib.TimeSignature,
            default=time_signature_lib.TimeSignature(4, 4))

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_signature_changed = \
            core.Callback[model_base.PropertyChange[time_signature_lib.TimeSignature]]()

    @property
    def track(self) -> Track:
        return cast(Track, self.parent)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        time_signature = self.get_property_value('time_signature')
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)


class MeasureReference(ProjectChild):
    class MeasureReferenceSpec(model_base.ObjectSpec):
        proto_type = 'measure_reference'
        proto_ext = project_pb2.measure_reference  # type: ignore

        measure = model_base.ObjectReferenceProperty(Measure)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.measure_changed = core.Callback[model_base.PropertyChange[Measure]]()

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


class MeasuredTrack(Track):  # pylint: disable=abstract-method
    class MeasuredSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.measured_track  # type: ignore

        measure_list = model_base.ObjectListProperty(MeasureReference)
        measure_heap = model_base.ObjectListProperty(Measure)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.measure_list_changed = core.Callback[model_base.PropertyListChange[MeasureReference]]()
        self.measure_heap_changed = core.Callback[model_base.PropertyListChange[Measure]]()

    def setup(self) -> None:
        super().setup()

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.measure_list_changed.add(self.__measure_list_changed)

    def __measure_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__add_measure(change.new_value)
        elif isinstance(change, model_base.PropertyListDelete):
            self.__remove_measure(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_measure(self, mref: MeasureReference) -> None:
        self.__listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda *_: self.__measure_changed(mref))
        self.duration_changed.call()

    def __remove_measure(self, mref: MeasureReference) -> None:
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.duration_changed.call()

    def __measure_changed(self, mref: MeasureReference) -> None:
        self.duration_changed.call()

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
    class NoteSpec(model_base.ObjectSpec):
        proto_type = 'note'
        proto_ext = project_pb2.note  # type: ignore

        pitches = model_base.WrappedProtoListProperty(pitch_lib.Pitch)
        base_duration = model_base.WrappedProtoProperty(
            audioproc.MusicalDuration,
            default=audioproc.MusicalDuration(1, 4))
        dots = model_base.Property(int, default=0)
        tuplet = model_base.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitches_changed = core.Callback[model_base.PropertyListChange[pitch_lib.Pitch]]()
        self.base_duration_changed = \
            core.Callback[model_base.PropertyChange[audioproc.MusicalDuration]]()
        self.dots_changed = core.Callback[model_base.PropertyChange[int]]()
        self.tuplet_changed = core.Callback[model_base.PropertyChange[int]]()

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

    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class ScoreMeasure(Measure):
    class ScoreMeasureSpec(model_base.ObjectSpec):
        proto_type = 'score_measure'
        proto_ext = project_pb2.score_measure  # type: ignore

        clef = model_base.WrappedProtoProperty(clef_lib.Clef, default=clef_lib.Clef.Treble)
        key_signature = model_base.WrappedProtoProperty(
            key_signature_lib.KeySignature,
            default=key_signature_lib.KeySignature('C major'))
        notes = model_base.ObjectListProperty(Note)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.clef_changed = core.Callback[model_base.PropertyChange[clef_lib.Clef]]()
        self.key_signature_changed = \
            core.Callback[model_base.PropertyChange[key_signature_lib.KeySignature]]()
        self.notes_changed = core.Callback[model_base.PropertyListChange[Note]]()

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()

        self.notes_changed.add(lambda _: self.content_changed.call())


class ScoreTrack(MeasuredTrack):
    class ScoreTrackSpec(model_base.ObjectSpec):
        proto_type = 'score_track'
        proto_ext = project_pb2.score_track  # type: ignore

        transpose_octaves = model_base.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.transpose_octaves_changed = core.Callback[model_base.PropertyChange[int]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.ScoreTrackDescription


class Beat(ProjectChild):
    class BeatSpec(model_base.ObjectSpec):
        proto_type = 'beat'
        proto_ext = project_pb2.beat  # type: ignore

        time = model_base.ProtoProperty(musical_time_pb2.MusicalDuration)
        velocity = model_base.Property(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = \
            core.Callback[model_base.PropertyChange[musical_time_pb2.MusicalDuration]]()
        self.velocity_changed = core.Callback[model_base.PropertyChange[int]]()

    @property
    def measure(self) -> 'BeatMeasure':
        return cast(BeatMeasure, self.parent)

    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class BeatMeasure(Measure):
    class BeatMeasureSpec(model_base.ObjectSpec):
        proto_type = 'beat_measure'
        proto_ext = project_pb2.beat_measure  # type: ignore

        beats = model_base.ObjectListProperty(Beat)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.beats_changed = core.Callback[model_base.PropertyListChange[Beat]]()

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()
        self.beats_changed.add(lambda _: self.content_changed.call())


class BeatTrack(MeasuredTrack):
    class BeatTrackSpec(model_base.ObjectSpec):
        proto_type = 'beat_track'
        proto_ext = project_pb2.beat_track  # type: ignore

        pitch = model_base.WrappedProtoProperty(pitch_lib.Pitch)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitch_changed = core.Callback[model_base.PropertyChange[pitch_lib.Pitch]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.BeatTrackDescription


class ControlPoint(ProjectChild):
    class ControlPointSpec(model_base.ObjectSpec):
        proto_type = 'control_point'
        proto_ext = project_pb2.control_point  # type: ignore

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        value = model_base.Property(float)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = core.Callback[model_base.PropertyChange[audioproc.MusicalTime]]()
        self.value_changed = core.Callback[model_base.PropertyChange[float]]()


class ControlTrack(Track):
    class ControlTrackSpec(model_base.ObjectSpec):
        proto_type = 'control_track'
        proto_ext = project_pb2.control_track  # type: ignore

        points = model_base.ObjectListProperty(ControlPoint)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.points_changed = core.Callback[model_base.PropertyListChange[ControlPoint]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.ControlTrackDescription


class SampleRef(ProjectChild):
    class SampleRefSpec(model_base.ObjectSpec):
        proto_type = 'sample_ref'
        proto_ext = project_pb2.sample_ref  # type: ignore

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        sample = model_base.ObjectReferenceProperty(Sample)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = core.Callback[model_base.PropertyChange[audioproc.MusicalTime]]()
        self.sample_changed = core.Callback[model_base.PropertyChange[Sample]]()


class SampleTrack(Track):
    class SampleTrackSpec(model_base.ObjectSpec):
        proto_type = 'sample_track'
        proto_ext = project_pb2.sample_track  # type: ignore

        samples = model_base.ObjectListProperty(SampleRef)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.samples_changed = core.Callback[model_base.PropertyListChange[SampleRef]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.SampleTrackDescription


class Metadata(ProjectChild):
    class MetadataSpec(model_base.ObjectSpec):
        proto_type = 'metadata'
        proto_ext = project_pb2.metadata  # type: ignore

        author = model_base.Property(str, allow_none=True)
        license = model_base.Property(str, allow_none=True)
        copyright = model_base.Property(str, allow_none=True)
        created = model_base.Property(int, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.author_changed = core.Callback[model_base.PropertyChange[str]]()
        self.license_changed = core.Callback[model_base.PropertyChange[str]]()
        self.copyright_changed = core.Callback[model_base.PropertyChange[str]]()
        self.created_changed = core.Callback[model_base.PropertyChange[int]]()


class Project(ObjectBase):
    class ProjectSpec(model_base.ObjectSpec):
        proto_type = 'project'
        proto_ext = project_pb2.project  # type: ignore

        metadata = model_base.ObjectProperty(Metadata)
        pipeline_graph_nodes = model_base.ObjectListProperty(BasePipelineGraphNode)
        pipeline_graph_connections = model_base.ObjectListProperty(PipelineGraphConnection)
        samples = model_base.ObjectListProperty(Sample)
        bpm = model_base.Property(int, default=120)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.metadata_changed = core.Callback[model_base.PropertyChange[Metadata]]()
        self.pipeline_graph_nodes_changed = \
            core.Callback[model_base.PropertyListChange[BasePipelineGraphNode]]()
        self.pipeline_graph_connections_changed = \
            core.Callback[model_base.PropertyListChange[PipelineGraphConnection]]()
        self.samples_changed = core.Callback[model_base.PropertyListChange[Sample]]()
        self.bpm_changed = core.Callback[model_base.PropertyChange[int]]()

        self.duration_changed = \
            core.Callback[model_base.PropertyChange[audioproc.MusicalDuration]]()
        self.pipeline_mutation = core.Callback[audioproc.Mutation]()

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(2 * 120, 4)  # 2min * 120bpm

    @property
    def project(self) -> 'Project':
        return self

    @property
    def attached_to_project(self) -> bool:
        return True

    def get_bpm(self, measure_idx: int, tick: int) -> int:  # pylint: disable=unused-argument
        return self.bpm

    @property
    def audio_out_node(self) -> AudioOutPipelineGraphNode:
        for node in self.get_property_value('pipeline_graph_nodes'):
            if isinstance(node, AudioOutPipelineGraphNode):
                return node

        raise ValueError("No audio out node found.")

    def get_node_description(self, uri: str) -> node_db.NodeDescription:
        raise NotImplementedError
