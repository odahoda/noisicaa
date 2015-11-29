#!/usr/bin/python3

import logging

from noisicaa import core

from noisicaa.audioproc.source.silence import SilenceSource
from noisicaa.audioproc.source.notes import NoteSource
from noisicaa.audioproc.source.fluidsynth import FluidSynthSource

from noisicaa.instr.library import Instrument
from noisicaa.instr.soundfont import SoundFont

from .time import Duration


logger = logging.getLogger(__name__)


class UpdateTrackProperties(core.Command):
    def __init__(self, name=None, visible=None, muted=None, volume=None,
                 transpose_octaves=None):
        super().__init__()
        self.name = name
        self.visible = visible
        self.muted = muted
        self.volume = volume
        self.transpose_octaves = transpose_octaves

    def run(self, track):
        assert isinstance(track, Track)

        if self.name is not None:
            track.name = self.name

        if self.visible is not None:
            track.visible = self.visible

        if self.muted is not None:
            track.muted = self.muted

        if self.volume is not None:
            track.volume = self.volume

        if self.transpose_octaves is not None:
            track.transpose_octaves = self.transpose_octaves


class ClearInstrument(core.Command):
    def run(self, track):
        assert isinstance(track, Track)

        track.instrument = None


class SetInstrument(core.Command):
    def __init__(self, instr):
        super().__init__()
        self.instr = instr

    def run(self, track):
        assert isinstance(track, Track)

        track.instrument = Instrument.from_json(self.instr)


class Measure(core.StateBase, core.CommandTarget):
    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)

        self.index = None

    @property
    def address(self):
        return self.parent.address + '/measure:%d' % self.index

    @property
    def track(self):
        return self.parent

    @property
    def sheet(self):
        return self.track.sheet

    @property
    def duration(self):
        time_signature = self.sheet.get_time_signature(self.index)
        return Duration(time_signature.upper, time_signature.lower)

    @property
    def empty(self):
        return False


class EventSource(object):
    def __init__(self, track):
        self._track = track
        self._sheet = track.sheet

    def get_events(self, start_timepos, end_timepos):
        raise NotImplementedError


class Track(core.StateBase, core.CommandTarget):
    measure_cls = None

    name = core.Property(str)
    instrument = core.ObjectProperty(cls=Instrument)
    measures = core.ObjectListProperty(cls=Measure)

    visible = core.Property(bool, default=True)
    muted = core.Property(bool, default=False)
    volume = core.Property(float, default=100.0)
    transpose_octaves = core.Property(int, default=0)

    def __init__(self, name=None, state=None):
        super().__init__()
        self.init_state(state)
        if state is None:
            self.name = name

        self.update_measures()
        self.index = None

    @property
    def address(self):
        return self.parent.address + '/track:%d' % self.index

    @property
    def sheet(self):
        return self.parent

    @property
    def project(self):
        return self.sheet.project

    def create_playback_source(self, pipeline):
        if self.instrument is None:
            source = SilenceSource()
            pipeline.add_node(source)
            source.setup()
            return source

        note_source = NoteSource(self)
        pipeline.add_node(note_source)
        note_source.setup()

        instr = self.instrument
        instr_source = FluidSynthSource(
            instr.path, instr.bank, instr.preset)
        pipeline.add_node(instr_source)
        instr_source.inputs['in'].connect(note_source.outputs['out'])
        instr_source.setup()

        return instr_source

    def update_measures(self):
        # This sure is very inefficient. Do we care?
        for idx, measure in enumerate(self.measures):
            measure.index = idx

    def append_measure(self):
        self.insert_measure(-1)

    def insert_measure(self, idx):
        assert idx == -1 or (0 <= idx <= len(self.measures) - 1)

        if idx == -1:
            idx = len(self.measures)

        if idx == 0 and len(self.measures) > 0:
            ref = self.measures[0]
        elif idx > 0:
            ref = self.measures[idx-1]
        else:
            ref = None
        measure = self.create_empty_measure(ref)
        measure.index = idx
        for i, m in enumerate(self.measures):
            m.index = i if i < idx else i + 1
        self.measures.insert(idx, measure)

    def remove_measure(self, idx):
        del self.measures[idx]
        self.update_measures()

    def create_empty_measure(self, ref):  # pylint: disable=unused-argument
        return self.measure_cls()  # pylint: disable=not-callable

    def create_event_source(self):
        raise NotImplementedError

    def get_sub_target(self, name):
        if name.startswith('measure:'):
            return self.measures[int(name[8:])]

        return super().get_sub_target(name)
