#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.audioproc.events import NoteOnEvent, NoteOffEvent

from .track import MeasuredTrack, Measure, EntitySource
from .time import Duration
from .pitch import Pitch
from . import model
from . import state
from . import commands
from . import mutations
from . import pipeline_graph
from . import misc
from . import time_mapper

logger = logging.getLogger(__name__)


class SetBeatTrackInstrument(commands.Command):
    instrument = core.Property(str)

    def __init__(self, instrument=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument = instrument

    def run(self, track):
        assert isinstance(track, BeatTrack)

        track.instrument = self.instrument
        track.instrument_node.update_pipeline()

commands.Command.register_command(SetBeatTrackInstrument)


class SetBeatTrackPitch(commands.Command):
    pitch = core.Property(Pitch)

    def __init__(self, pitch=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.pitch = pitch

    def run(self, track):
        assert isinstance(track, BeatTrack)

        track.pitch = self.pitch

commands.Command.register_command(SetBeatTrackPitch)


class SetBeatVelocity(commands.Command):
    velocity = core.Property(int)

    def __init__(self, velocity=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.velocity = velocity

    def run(self, beat):
        assert isinstance(beat, Beat)

        beat.velocity = self.velocity

commands.Command.register_command(SetBeatVelocity)


class AddBeat(commands.Command):
    timepos = core.Property(Duration)

    def __init__(self, timepos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.timepos = timepos

    def run(self, measure):
        assert isinstance(measure, BeatMeasure)

        beat = Beat(timepos=self.timepos, velocity=100)
        assert 0 <= beat.timepos < measure.duration
        measure.beats.append(beat)

commands.Command.register_command(AddBeat)


class RemoveBeat(commands.Command):
    beat_id = core.Property(str)

    def __init__(self, beat_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.beat_id = beat_id

    def run(self, measure):
        assert isinstance(measure, BeatMeasure)

        root = measure.root
        beat = root.get_object(self.beat_id)
        assert beat.is_child_of(measure)
        del measure.beats[beat.index]

commands.Command.register_command(RemoveBeat)


class Beat(model.Beat, state.StateBase):
    def __init__(self,
                 timepos=None, velocity=None,
                 state=None):
        super().__init__(state=state)
        if state is None:
            self.timepos = timepos
            self.velocity = velocity

state.StateBase.register_class(Beat)


class BeatMeasure(model.BeatMeasure, Measure):
    def __init__(self, state=None):
        super().__init__(state=state)

    @property
    def empty(self):
        return len(self.beats) == 0

state.StateBase.register_class(BeatMeasure)


class BeatEntitySource(EntitySource):
    def __init__(self, track):
        super().__init__(track)
        self._time_mapper = time_mapper.TimeMapper(track.sheet)
        self._current_micro_sample_pos = 0
        self._current_tick = 0
        self._current_measure = 0

    def get_events(self, start_sample_pos, end_sample_pos):
        # logger.debug("get_events(%d, %d)", start_sample_pos, end_sample_pos)

        if self._current_micro_sample_pos >= 1000000 * start_sample_pos:
            self._current_measure = 0
            self._current_tick = 0
            self._current_micro_sample_pos = 0

        while self._current_micro_sample_pos < 1000000 * end_sample_pos:
            sample_pos = self._current_micro_sample_pos // 1000000
            measure = self._track.measure_list[self._current_measure].measure

            if self._current_micro_sample_pos >= 1000000 * start_sample_pos:
                for beat in measure.beats:
                    if beat.timepos.ticks == self._current_tick:
                        yield NoteOnEvent(
                            sample_pos, self._track.pitch, volume=beat.velocity)

            bpm = self._track.sheet.get_bpm(measure.index, self._current_tick)
            micro_samples_per_tick = int(
                1000000 * 4 * 44100 * 60 // bpm * Duration.tick_duration)

            self._current_micro_sample_pos += micro_samples_per_tick
            self._current_tick += 1
            if self._current_tick >= measure.duration.ticks:
                self._current_tick = 0
                self._current_measure += 1
                if self._current_measure >= len(self._track.measure_list):
                    self._current_measure = 0


class BeatTrack(model.BeatTrack, MeasuredTrack):
    measure_cls = BeatMeasure

    def __init__(
            self, instrument=None, pitch=None, num_measures=1,
            state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            if instrument is None:
                self.instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=128&preset=0'
            else:
                self.instrument = instrument

            if pitch is None:
                self.pitch = Pitch('B2')
            else:
                self.pitch = pitch

            for _ in range(num_measures):
                self.append_measure()

    def create_entity_source(self):
        return BeatEntitySource(self)

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    @property
    def event_source_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.EventSourcePipelineGraphNode) and node.track is self:
                return node

        raise ValueError("No event source node found.")

    @property
    def instr_name(self):
        return '%s-instr' % self.id

    @property
    def instrument_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.InstrumentPipelineGraphNode) and node.track is self:
                return node

        raise ValueError("No instrument node found.")

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        instrument_node = pipeline_graph.InstrumentPipelineGraphNode(
            name="Track Instrument",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(instrument_node)

        conn = pipeline_graph.PipelineGraphConnection(
            instrument_node, 'out', self.mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

        event_source_node = pipeline_graph.EventSourcePipelineGraphNode(
            name="Track Events",
            graph_pos=instrument_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(event_source_node)

        conn = pipeline_graph.PipelineGraphConnection(
            event_source_node, 'out', instrument_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.event_source_node)
        self.sheet.remove_pipeline_graph_node(self.instrument_node)
        super().remove_pipeline_nodes()

state.StateBase.register_class(BeatTrack)
