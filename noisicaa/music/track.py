#!/usr/bin/python3

import logging

from noisicaa import core

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

        if track.instrument is not None:
            track.remove_instrument_from_pipeline()

        track.instrument = None

commands.Command.register_command(ClearInstrument)


class SetInstrument(commands.Command):
    instrument_type = core.Property(str)
    instrument_args = core.DictProperty()

    def __init__(self, instrument_type=None, instrument_args=None,
                 state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument_type = instrument_type
            self.instrument_args.update(instrument_args)

    def run(self, track):
        assert isinstance(track, Track)

        assert self.instrument_type == 'SoundFontInstrument'
        instr = instrument.SoundFontInstrument(**self.instrument_args)

        if track.instrument is not None:
            track.remove_instrument_from_pipeline()
        track.instrument = instr
        track.add_instrument_to_pipeline()

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
        return self.instrument.pipeline_node_id

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    def add_mixer_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'passthru', self.mixer_name, 'track-mixer'))
        self.sheet.handle_pipeline_mutation(
            mutations.ConnectPorts(
                self.mixer_name, 'out',
                self.sheet.main_mixer_name, 'in'))

    def remove_mixer_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.DisconnectPorts(
                self.mixer_name, 'out',
                self.sheet.main_mixer_name, 'in'))
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.mixer_name))

    def add_instrument_to_pipeline(self):
        self.instrument.add_to_pipeline()

        self.sheet.handle_pipeline_mutation(
            mutations.ConnectPorts(
                self.instr_name, 'out', self.mixer_name, 'in'))

        self.sheet.handle_pipeline_mutation(
            mutations.ConnectPorts(
                self.event_source_name, 'out', self.instr_name, 'in'))

    def remove_instrument_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.DisconnectPorts(
                self.instr_name, 'out', self.mixer_name, 'in'))

        self.sheet.handle_pipeline_mutation(
            mutations.DisconnectPorts(
                self.event_source_name, 'out', self.instr_name, 'in'))

        self.instrument.remove_from_pipeline()

    def add_event_source_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'track_event_source', self.event_source_name, 'events',
                queue_name='track:%s' % self.id))

    def remove_event_source_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.event_source_name))

    def add_to_pipeline(self):
        self.add_mixer_to_pipeline()
        self.add_event_source_to_pipeline()
        if self.instrument is not None:
            self.add_instrument_to_pipeline()

    def remove_from_pipeline(self):
        if self.instrument is not None:
            self.remove_instrument_from_pipeline()
        self.remove_event_source_from_pipeline()
        self.remove_mixer_from_pipeline()
