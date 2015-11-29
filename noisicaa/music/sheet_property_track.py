#!/usr/bin/python3

import logging

from noisicaa.core import (
    Property,
    Command
)

from .time_signature import TimeSignature
from .track import Track, Measure, EventSource

logger = logging.getLogger(__name__)

# pylint: disable=multiple-statements
class SetTimeSignature(Command):
    def __init__(self, upper, lower):
        super().__init__()
        self.upper = upper
        self.lower = lower

    def run(self, measure):
        assert isinstance(measure, SheetPropertyMeasure)

        measure.time_signature = TimeSignature(self.upper, self.lower)


class SetBPM(Command):
    def __init__(self, bpm):
        super().__init__()
        self.bpm = bpm

    def run(self, measure):
        assert isinstance(measure, SheetPropertyMeasure)

        if self.bpm <= 0 or self.bpm > 10000:
            raise ValueError

        measure.bpm = self.bpm


class SheetPropertyMeasure(Measure):
    bpm = Property(int, default=120)
    time_signature = Property(TimeSignature, default=TimeSignature(4, 4))

    def __init__(self, state=None):
        super().__init__(state)
        if state is None:
            pass

    @property
    def empty(self):
        return True

Measure.register_subclass(SheetPropertyMeasure)


class SheetPropertyEventSource(EventSource):
    def __init__(self, track):
        super().__init__(track)

    def get_events(self, start_timepos, end_timepos):
        return
        yield  # pylint: disable=unreachable


class SheetPropertyTrack(Track):
    measure_cls = SheetPropertyMeasure

    def __init__(self, name=None, num_measures=1, state=None):
        super().__init__(name, state)

        if state is None:
            for _ in range(num_measures):
                self.measures.append(SheetPropertyMeasure())
            self.update_measures()

    @property
    def address(self):
        return self.parent.address + '/property_track'

    def create_empty_measure(self, ref):
        measure = super().create_empty_measure(ref)

        if ref is not None:
            measure.bpm = ref.bpm
            measure.time_signature = ref.time_signature

        return measure

    def create_event_source(self):
        return SheetPropertyEventSource(self)

Track.register_subclass(SheetPropertyTrack)
