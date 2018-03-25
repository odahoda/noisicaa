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

# mypy: loose
# TODO: pylint-unclean

import fractions

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import instrument_db
from . import pitch
from . import clef
from . import key_signature
from . import time_signature
from . import misc


class ProjectChild(core.ObjectBase):
    @property
    def project(self):
        return self.root


class Track(ProjectChild):
    name = core.Property(str)

    visible = core.Property(bool, default=True)
    muted = core.Property(bool, default=False)
    gain = core.Property(float, default=0.0)
    pan = core.Property(float, default=0.0)

    mixer_id = core.Property(str, allow_none=True)

    @property
    def duration(self):
        return audioproc.MusicalDuration(1, 1)

    @property
    def is_master_group(self):
        return False

    def walk_tracks(self, groups=False, tracks=True):
        if tracks:
            yield self


class Measure(ProjectChild):
    @property
    def track(self):
        return self.parent

    @property
    def duration(self):
        time_signature = self.project.get_time_signature(self.index)
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)


class MeasureReference(ProjectChild):
    measure_id = core.Property(str)

    @property
    def measure(self):
        return self.root.get_object(self.measure_id)

    @property
    def track(self):
        return self.parent


class MeasuredTrack(Track):
    measure_list = core.ObjectListProperty(cls=MeasureReference)
    measure_heap = core.ObjectListProperty(cls=Measure)

    @property
    def duration(self):
        duration = audioproc.MusicalDuration()
        for mref in self.measure_list:
            duration += mref.measure.duration
        return duration


class Note(ProjectChild):
    pitches = core.ListProperty(pitch.Pitch)
    base_duration = core.Property(audioproc.MusicalDuration, default=audioproc.MusicalDuration(1, 4))
    dots = core.Property(int, default=0)
    tuplet = core.Property(int, default=0)

    @property
    def measure(self):
        return self.parent

    @property
    def is_rest(self):
        return len(self.pitches) == 1 and self.pitches[0].is_rest

    @property
    def max_allowed_dots(self):
        if self.base_duration <= audioproc.MusicalDuration(1, 32):
            return 0
        if self.base_duration <= audioproc.MusicalDuration(1, 16):
            return 1
        if self.base_duration <= audioproc.MusicalDuration(1, 8):
            return 2
        return 3

    @property
    def duration(self):
        duration = self.base_duration
        for _ in range(self.dots):
            duration *= fractions.Fraction(3, 2)
        if self.tuplet == 3:
            duration *= fractions.Fraction(2, 3)
        elif self.tuplet == 5:
            duration *= fractions.Fraction(4, 5)
        return audioproc.MusicalDuration(duration)


class TrackGroup(Track):
    tracks = core.ObjectListProperty(Track)

    @property
    def duration(self):
        duration = audioproc.MusicalDuration()
        for track in self.tracks:
            duration = max(duration, track.duration)
        return duration

    def walk_tracks(self, groups=False, tracks=True):
        if groups:
            yield self

        for track in self.tracks:
            yield from track.walk_tracks(groups, tracks)


class MasterTrackGroup(TrackGroup):
    @property
    def is_master_group(self):
        return True


class ScoreMeasure(Measure):
    clef = core.Property(clef.Clef, default=clef.Clef.Treble)
    key_signature = core.Property(
        key_signature.KeySignature,
        default=key_signature.KeySignature('C major'))
    notes = core.ObjectListProperty(cls=Note)

    @property
    def time_signature(self):
        return self.project.get_time_signature(self.index)


class ScoreTrack(MeasuredTrack):
    instrument = core.Property(str)
    transpose_octaves = core.Property(int, default=0)

    instrument_id = core.Property(str, allow_none=True)
    event_source_id = core.Property(str, allow_none=True)


class Beat(ProjectChild):
    time = core.Property(audioproc.MusicalDuration)
    velocity = core.Property(int)

    @property
    def measure(self):
        return self.parent


class BeatMeasure(Measure):
    beats = core.ObjectListProperty(Beat)

    @property
    def time_signature(self):
        return self.project.get_time_signature(self.index)


class BeatTrack(MeasuredTrack):
    instrument = core.Property(str)
    pitch = core.Property(pitch.Pitch)

    instrument_id = core.Property(str, allow_none=True)
    event_source_id = core.Property(str, allow_none=True)


class PropertyMeasure(Measure):
    time_signature = core.Property(
        time_signature.TimeSignature,
        default=time_signature.TimeSignature(4, 4))


class PropertyTrack(MeasuredTrack):
    pass


class ControlPoint(ProjectChild):
    time = core.Property(audioproc.MusicalTime)
    value = core.Property(float)


class ControlTrack(Track):
    points = core.ObjectListProperty(ControlPoint)
    generator_id = core.Property(str, allow_none=True)


class SampleRef(ProjectChild):
    time = core.Property(audioproc.MusicalTime)
    sample_id = core.Property(str)

    @property
    def sample(self):
        return self.root.get_object(self.sample_id)


class SampleTrack(Track):
    samples = core.ObjectListProperty(SampleRef)
    sample_script_id = core.Property(str, allow_none=True)


class PipelineGraphControlValue(ProjectChild):
    name = core.Property(str)
    value = core.Property(float)


class PipelineGraphPortPropertyValue(ProjectChild):
    port_name = core.Property(str)
    name = core.Property(str)
    value = core.Property((str, float, int, bool))


class BasePipelineGraphNode(ProjectChild):
    name = core.Property(str)
    graph_pos = core.Property(misc.Pos2F)
    control_values = core.ObjectListProperty(PipelineGraphControlValue)
    port_property_values = core.ObjectListProperty(PipelineGraphPortPropertyValue)

    @property
    def removable(self):
        raise NotImplementedError

    @property
    def description(self):
        raise NotImplementedError


class PipelineGraphNode(BasePipelineGraphNode):
    node_uri = core.Property(str)

    @property
    def removable(self):
        return True

    @property
    def description(self):
        return self.project.get_node_description(self.node_uri)


class AudioOutPipelineGraphNode(BasePipelineGraphNode):
    @property
    def removable(self):
        return False

    @property
    def description(self):
        return node_db.Builtins.RealmSinkDescription


class TrackMixerPipelineGraphNode(BasePipelineGraphNode):
    track_id = core.Property(str)

    @property
    def track(self):
        return self.root.get_object(self.track_id)

    @track.setter
    def track(self, obj):
        self.track_id = obj.id

    @property
    def removable(self):
        return False

    @property
    def description(self):
        return node_db.Builtins.TrackMixerDescription


class PianoRollPipelineGraphNode(BasePipelineGraphNode):
    track_id = core.Property(str)

    @property
    def track(self):
        return self.root.get_object(self.track_id)

    @track.setter
    def track(self, obj):
        self.track_id = obj.id

    @property
    def removable(self):
        return False

    @property
    def description(self):
        return node_db.Builtins.PianoRollDescription


class CVGeneratorPipelineGraphNode(BasePipelineGraphNode):
    track_id = core.Property(str)

    @property
    def track(self):
        return self.root.get_object(self.track_id)

    @track.setter
    def track(self, obj):
        self.track_id = obj.id

    @property
    def removable(self):
        return False

    @property
    def description(self):
        return node_db.Builtins.CVGeneratorDescription


class SampleScriptPipelineGraphNode(BasePipelineGraphNode):
    track_id = core.Property(str)

    @property
    def track(self):
        return self.root.get_object(self.track_id)

    @track.setter
    def track(self, obj):
        self.track_id = obj.id

    @property
    def removable(self):
        return False

    @property
    def description(self):
        return node_db.Builtins.SampleScriptDescription


class InstrumentPipelineGraphNode(BasePipelineGraphNode):
    track_id = core.Property(str)

    @property
    def track(self):
        return self.root.get_object(self.track_id)

    @track.setter
    def track(self, obj):
        self.track_id = obj.id

    @property
    def removable(self):
        return False

    @property
    def description(self):
        return instrument_db.parse_uri(self.track.instrument, self.project.get_node_description)


class PipelineGraphConnection(ProjectChild):
    source_node_id = core.Property(str)
    source_port = core.Property(str)
    dest_node_id = core.Property(str)
    dest_port = core.Property(str)

    @property
    def source_node(self):
        return self.root.get_object(self.source_node_id)

    @source_node.setter
    def source_node(self, obj):
        self.source_node_id = obj.id

    @property
    def dest_node(self):
        return self.root.get_object(self.dest_node_id)

    @dest_node.setter
    def dest_node(self, obj):
        self.dest_node_id = obj.id


class Sample(ProjectChild):
    path = core.Property(str)


class Metadata(ProjectChild):
    author = core.Property(str, allow_none=True)
    license = core.Property(str, allow_none=True)
    copyright = core.Property(str, allow_none=True)
    created = core.Property(int, allow_none=True)


class Project(core.ObjectBase):
    metadata = core.ObjectProperty(cls=Metadata)
    master_group = core.ObjectProperty(TrackGroup)
    property_track = core.ObjectProperty(PropertyTrack)
    pipeline_graph_nodes = core.ObjectListProperty(PipelineGraphNode)
    pipeline_graph_connections = core.ObjectListProperty(PipelineGraphConnection)
    samples = core.ObjectListProperty(Sample)
    bpm = core.Property(int, default=120)

    @property
    def duration(self):
        self.master_group.duration

    @property
    def all_tracks(self):
        return ([self.property_track]
                + list(self.master_group.walk_tracks()))

    def get_bpm(self, measure_idx, tick):  # pylint: disable=unused-argument
        return self.bpm

    def get_time_signature(self, measure_idx):
        # TODO: this is called with an incorrect measure_idx (index of the measure within the
        #   measure_heap), so always use the time signature from the first measure, which
        #   is also wrong, but at least doesn't crash.
        return self.property_track.measure_list[0].measure.time_signature


    def get_node_description(self, uri):
        raise NotImplementedError
