#!/usr/bin/python3

import logging

from noisicaa import core

from noisicaa.audioproc.source.silence import SilenceSource
from noisicaa.audioproc.source.notes import NoteSource
from noisicaa.audioproc.source.fluidsynth import FluidSynthSource

from .time import Duration
from . import model
from . import state
from . import commands
from . import instrument
from . import mutations

logger = logging.getLogger(__name__)


class UpdateTrackProperties(commands.Command):
    name = core.Property(str, allow_none=True)
    visible = core.Property(bool, allow_none=True)
    muted = core.Property(bool, allow_none=True)
    volume = core.Property(float, allow_none=True)
    transpose_octaves = core.Property(int, allow_none=True)

    def __init__(self, name=None, visible=None, muted=None, volume=None,
                 transpose_octaves=None, state=None):
        super().__init__(state=state)
        if state is None:
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

commands.Command.register_command(UpdateTrackProperties)


class ClearInstrument(commands.Command):
    def run(self, track):
        assert isinstance(track, Track)

        track.instrument = None

commands.Command.register_command(ClearInstrument)


class SetInstrument(commands.Command):
    instr = core.DictProperty()

    def __init__(self, instr=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.instr.update(instr)

    def run(self, track):
        assert isinstance(track, Track)

        track.instrument = instrument.Instrument.from_json(self.instr)

commands.Command.register_command(SetInstrument)


class Measure(model.Measure, state.StateBase):
    def __init__(self, state=None):
        super().__init__(state)

    @property
    def empty(self):
        return False


class EventSource(object):
    def __init__(self, track):
        self._track = track
        self._sheet = track.sheet

    def get_events(self, start_timepos, end_timepos):
        raise NotImplementedError


class Track(model.Track, state.StateBase):
    measure_cls = None

    def __init__(self, name=None, instrument=None, state=None):
        super().__init__(state)

        if state is None:
            self.name = name
            self.instrument = instrument

    @property
    def project(self):
        return self.sheet.project

    def create_playback_source(self, pipeline, setup=True, recursive=False):
        if self.instrument is None:
            source = SilenceSource()
            pipeline.add_node(source)
            if setup:
                source.setup()
            return source

        note_source = NoteSource(self)
        pipeline.add_node(note_source)
        if setup:
            note_source.setup()

        instr = self.instrument
        instr_source = FluidSynthSource(
            instr.path, instr.bank, instr.preset)
        instr_source.outputs['out'].volume = self.volume
        instr_source.outputs['out'].muted = self.muted
        pipeline.add_node(instr_source)
        instr_source.inputs['in'].connect(note_source.outputs['out'])
        if setup:
            instr_source.setup()

        return instr_source

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
        self.measures.insert(idx, measure)

    def remove_measure(self, idx):
        del self.measures[idx]

    def create_empty_measure(self, ref):  # pylint: disable=unused-argument
        return self.measure_cls()  # pylint: disable=not-callable

    def create_event_source(self):
        raise NotImplementedError

    @property
    def mixer_name(self):
        return '%s-track-mixer' % self.id

    @property
    def instr_name(self):
        return '%s-instr' % self.id

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    def add_to_pipeline(self):
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.AddNode(
                'passthru', self.mixer_name, 'track-mixer'))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.ConnectPorts(
                self.mixer_name, 'out',
                self.sheet.main_mixer_name, 'in'))

        self.project.listeners.call(
            'pipeline_mutations',
            mutations.AddNode(
                'fluidsynth', self.instr_name, 'instrument',
                soundfont_path='/usr/share/sounds/sf2/FluidR3_GM.sf2',
                bank=0, preset=0))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.ConnectPorts(
                self.instr_name, 'out', self.mixer_name, 'in'))

        self.project.listeners.call(
            'pipeline_mutations',
            mutations.AddNode(
                'track_event_source', self.event_source_name, 'events'))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.ConnectPorts(
                self.event_source_name, 'out', self.instr_name, 'in'))

    def remove_from_pipeline(self):
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.DisconnectPorts(
                self.event_source_name, 'out', self.instr_name, 'in'))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.RemoveNode(self.event_source_name))

        self.project.listeners.call(
            'pipeline_mutations',
            mutations.DisconnectPorts(
                self.instr_name, 'out', self.mixer_name, 'in'))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.RemoveNode(self.instr_name))

        self.project.listeners.call(
            'pipeline_mutations',
            mutations.DisconnectPorts(
                self.mixer_name, 'out',
                self.sheet.main_mixer_name, 'in'))
        self.project.listeners.call(
            'pipeline_mutations',
            mutations.RemoveNode(self.mixer_name))


