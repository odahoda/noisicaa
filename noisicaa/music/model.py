#/usr/bin/python3

import fractions

from noisicaa import core
from noisicaa import node_db
from . import pitch
from . import time
from . import clef
from . import key_signature
from . import time_signature
from . import misc


class Instrument(core.ObjectBase):
    name = core.Property(str)
    library_id = core.Property(str, allow_none=True)


class SoundFontInstrument(Instrument):
    path = core.Property(str)
    bank = core.Property(int)
    preset = core.Property(int)


class SampleInstrument(Instrument):
    path = core.Property(str)


class Measure(core.ObjectBase):
    @property
    def track(self):
        return self.parent

    @property
    def sheet(self):
        return self.track.sheet

    @property
    def duration(self):
        time_signature = self.sheet.get_time_signature(self.index)
        return time.Duration(time_signature.upper, time_signature.lower)


class MeasureReference(core.ObjectBase):
    measure = core.ObjectReferenceProperty(allow_none=True)

    @property
    def track(self):
        return self.parent

    @property
    def sheet(self):
        return self.track.sheet


class Track(core.ObjectBase):
    name = core.Property(str)
    measure_list = core.ObjectListProperty(cls=MeasureReference)
    measure_heap = core.ObjectListProperty(cls=Measure)

    visible = core.Property(bool, default=True)
    muted = core.Property(bool, default=False)
    volume = core.Property(float, default=100.0)

    @property
    def sheet(self):
        return self.parent.sheet

    def walk_tracks(self, groups=False, tracks=True):
        if tracks:
            yield self


class Note(core.ObjectBase):
    pitches = core.ListProperty(pitch.Pitch)
    base_duration = core.Property(time.Duration, default=time.Duration(1, 4))
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
        if self.base_duration <= time.Duration(1, 32):
            return 0
        if self.base_duration <= time.Duration(1, 16):
            return 1
        if self.base_duration <= time.Duration(1, 8):
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
        return time.Duration(duration)


class TrackGroup(Track):
    tracks = core.ObjectListProperty(Track)

    def walk_tracks(self, groups=False, tracks=True):
        if groups:
            yield self

        for track in self.tracks:
            yield from track.walk_tracks(groups, tracks)


class MasterTrackGroup(TrackGroup):
    pass


class ScoreMeasure(Measure):
    clef = core.Property(clef.Clef, default=clef.Clef.Treble)
    key_signature = core.Property(
        key_signature.KeySignature,
        default=key_signature.KeySignature('C major'))
    notes = core.ObjectListProperty(cls=Note)

    @property
    def time_signature(self):
        return self.sheet.get_time_signature(self.index)


class ScoreTrack(Track):
    instrument = core.ObjectProperty(cls=Instrument)
    transpose_octaves = core.Property(int, default=0)


class Beat(core.ObjectBase):
    timepos = core.Property(time.Duration)
    velocity = core.Property(int)

    @property
    def measure(self):
        return self.parent


class BeatMeasure(Measure):
    beats = core.ObjectListProperty(Beat)

    @property
    def time_signature(self):
        return self.sheet.get_time_signature(self.index)


class BeatTrack(Track):
    instrument = core.ObjectProperty(cls=Instrument)
    pitch = core.Property(pitch.Pitch)
    measure_sequence = core.ObjectReferenceProperty(BeatMeasure)


class SheetPropertyMeasure(Measure):
    bpm = core.Property(int, default=120)
    time_signature = core.Property(
        time_signature.TimeSignature,
        default=time_signature.TimeSignature(4, 4))


class SheetPropertyTrack(Track):
    pass


class PipelineGraphNodeParameterValue(core.ObjectBase):
    name = core.Property(str)
    value = core.Property((str, float, int))


class PipelineGraphPortPropertyValue(core.ObjectBase):
    port_name = core.Property(str)
    name = core.Property(str)
    value = core.Property((str, float, int, bool))


class BasePipelineGraphNode(core.ObjectBase):
    name = core.Property(str)
    graph_pos = core.Property(misc.Pos2F)
    parameter_values = core.ObjectListProperty(PipelineGraphNodeParameterValue)
    port_property_values = core.ObjectListProperty(PipelineGraphPortPropertyValue)

    @property
    def sheet(self):
        return self.parent

    @property
    def project(self):
        return self.sheet.project

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

    __description = node_db.SystemNodeDescription(
        ports=[
            node_db.AudioPortDescription(
                name='in',
                direction=node_db.PortDirection.Input),
        ])

    @property
    def description(self):
        return self.__description


class TrackMixerPipelineGraphNode(BasePipelineGraphNode):
    track = core.ObjectReferenceProperty()

    @property
    def removable(self):
        return False

    __description = node_db.SystemNodeDescription(
        ports=[
            node_db.AudioPortDescription(
                name='in',
                direction=node_db.PortDirection.Input),
            node_db.AudioPortDescription(
                name='out',
                direction=node_db.PortDirection.Output),
        ])

    @property
    def description(self):
        return self.__description


class EventSourcePipelineGraphNode(BasePipelineGraphNode):
    track = core.ObjectReferenceProperty()

    @property
    def removable(self):
        return False

    __description = node_db.SystemNodeDescription(
        ports=[
            node_db.EventPortDescription(
                name='out',
                direction=node_db.PortDirection.Output),
        ])

    @property
    def description(self):
        return self.__description


class InstrumentPipelineGraphNode(BasePipelineGraphNode):
    track = core.ObjectReferenceProperty()

    @property
    def removable(self):
        return False

    __description = node_db.SystemNodeDescription(
        ports=[
            node_db.EventPortDescription(
                name='in',
                direction=node_db.PortDirection.Input),
            node_db.AudioPortDescription(
                name='out',
                direction=node_db.PortDirection.Output),
        ])

    @property
    def description(self):
        return self.__description


class PipelineGraphConnection(core.ObjectBase):
    source_node = core.ObjectReferenceProperty()
    source_port = core.Property(str)
    dest_node = core.ObjectReferenceProperty()
    dest_port = core.Property(str)


class Sheet(core.ObjectBase):
    name = core.Property(str, default="Sheet")
    master_group = core.ObjectProperty(TrackGroup)
    property_track = core.ObjectProperty(SheetPropertyTrack)
    pipeline_graph_nodes = core.ObjectListProperty(PipelineGraphNode)
    pipeline_graph_connections = core.ObjectListProperty(
        PipelineGraphConnection)

    @property
    def sheet(self):
        return self

    @property
    def project(self):
        return self.parent

    def get_bpm(self, measure_idx, tick):  # pylint: disable=unused-argument
        return self.property_track.measure_list[measure_idx].measure.bpm

    def get_time_signature(self, measure_idx):
        return self.property_track.measure_list[measure_idx].measure.time_signature


class Metadata(core.ObjectBase):
    author = core.Property(str, allow_none=True)
    license = core.Property(str, allow_none=True)
    copyright = core.Property(str, allow_none=True)
    created = core.Property(int, allow_none=True)


class Project(core.ObjectBase):
    sheets = core.ObjectListProperty(cls=Sheet)
    current_sheet = core.Property(int, default=0)
    metadata = core.ObjectProperty(cls=Metadata)

    def get_current_sheet(self):
        return self.sheets[self.current_sheet]

    def get_sheet(self, name):
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        raise ValueError("No sheet %r" % name)

    def get_sheet_index(self, name):
        for idx, sheet in enumerate(self.sheets):
            if sheet.name == name:
                return idx
        raise ValueError("No sheet %r" % name)

    def get_node_description(self, uri):
        raise NotImplementedError
