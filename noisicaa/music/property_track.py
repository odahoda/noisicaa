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

import logging

from noisicaa import core

from .time_signature import TimeSignature
from . import model
from . import commands
from . import state
from . import base_track

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
        assert isinstance(measure, PropertyMeasure)

        measure.time_signature = TimeSignature(self.upper, self.lower)

commands.Command.register_command(SetTimeSignature)


class PropertyMeasure(model.PropertyMeasure, base_track.Measure):
    def __init__(self, state=None):
        super().__init__(state)
        if state is None:
            pass

    @property
    def empty(self):
        return True

state.StateBase.register_class(PropertyMeasure)


class PropertyTrack(model.PropertyTrack, base_track.MeasuredTrack):
    measure_cls = PropertyMeasure

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

state.StateBase.register_class(PropertyTrack)
