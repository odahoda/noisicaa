#!/usr/bin/python3

import logging

from noisicaa import core

from .time_signature import TimeSignature
from .track import Track, Measure, EventSource
from .time import Duration
from . import model
from . import commands
from . import state

logger = logging.getLogger(__name__)


class SetTimeSignature(commands.Command):
    upper = core.Property(int)
    lower = core.Property(int)

    def __init__(self, upper=None, lower=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.upper = upper
            self.lower = lower

    def run(self, measure):
        assert isinstance(measure, SheetPropertyMeasure)

        measure.time_signature = TimeSignature(self.upper, self.lower)

commands.Command.register_command(SetTimeSignature)


class SetBPM(commands.Command):
    bpm = core.Property(int)

    def __init__(self, bpm=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.bpm = bpm

    def run(self, measure):
        assert isinstance(measure, SheetPropertyMeasure)

        if self.bpm <= 0 or self.bpm > 10000:
            raise ValueError

        measure.bpm = self.bpm

commands.Command.register_command(SetBPM)


class SheetPropertyMeasure(model.SheetPropertyMeasure, Measure):
    def __init__(self, state=None):
        super().__init__(state)
        if state is None:
            pass

    @property
    def empty(self):
        return True

    def get_num_samples(self, sample_rate):
        return int(
            sample_rate
            * Duration(self.time_signature.upper, self.time_signature.lower)
            * 4 * 60 // self.bpm)

state.StateBase.register_class(SheetPropertyMeasure)


class SheetPropertyEventSource(EventSource):
    def __init__(self, track):
        super().__init__(track)

    def get_events(self, start_timepos, end_timepos):
        return
        yield  # pylint: disable=unreachable


class SheetPropertyTrack(model.SheetPropertyTrack, Track):
    measure_cls = SheetPropertyMeasure

    def __init__(self, name=None, num_measures=1, state=None):
        super().__init__(name=name, state=state)

        if state is None:
            for _ in range(num_measures):
                self.measures.append(SheetPropertyMeasure())

    def create_empty_measure(self, ref):
        measure = super().create_empty_measure(ref)

        if ref is not None:
            measure.bpm = ref.bpm
            measure.time_signature = ref.time_signature

        return measure

    def create_event_source(self):
        return SheetPropertyEventSource(self)

    def get_num_samples(self, sample_rate):
        return sum((m.get_num_samples(sample_rate) for m in self.measures), 0)

state.StateBase.register_class(SheetPropertyTrack)
