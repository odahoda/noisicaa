#!/usr/bin/python3

import logging

from noisicaa import core

from .time_signature import TimeSignature
from .track import MeasuredTrack, Measure
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


class SheetPropertyMeasure(model.SheetPropertyMeasure, Measure):
    def __init__(self, state=None):
        super().__init__(state)
        if state is None:
            pass

    @property
    def empty(self):
        return True

state.StateBase.register_class(SheetPropertyMeasure)


class SheetPropertyTrack(model.SheetPropertyTrack, MeasuredTrack):
    measure_cls = SheetPropertyMeasure

    def __init__(self, name=None, num_measures=1, state=None):
        super().__init__(name=name, state=state)

        if state is None:
            for _ in range(num_measures):
                self.append_measure()

    def create_empty_measure(self, ref):
        measure = super().create_empty_measure(ref)

        if ref is not None:
            measure.time_signature = ref.time_signature

        return measure

state.StateBase.register_class(SheetPropertyTrack)
