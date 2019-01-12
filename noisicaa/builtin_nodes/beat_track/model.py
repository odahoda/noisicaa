#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

from typing import cast, Any

from noisicaa import core
from noisicaa import node_db
from noisicaa import model
from noisicaa.audioproc.public import musical_time_pb2
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description


class Beat(model.ProjectChild):
    class BeatSpec(model.ObjectSpec):
        proto_type = 'beat'
        proto_ext = model_registry_pb2.beat

        time = model.ProtoProperty(musical_time_pb2.MusicalDuration)
        velocity = model.Property(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = \
            core.Callback[model.PropertyChange[musical_time_pb2.MusicalDuration]]()
        self.velocity_changed = core.Callback[model.PropertyChange[int]]()

    @property
    def measure(self) -> 'BeatMeasure':
        return cast(BeatMeasure, self.parent)

    def property_changed(self, change: model.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class BeatMeasure(model.Measure):
    class BeatMeasureSpec(model.ObjectSpec):
        proto_type = 'beat_measure'
        proto_ext = model_registry_pb2.beat_measure

        beats = model.ObjectListProperty(Beat)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.beats_changed = core.Callback[model.PropertyListChange[Beat]]()

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()
        self.beats_changed.add(lambda _: self.content_changed.call())


class BeatTrack(model.MeasuredTrack):
    class BeatTrackSpec(model.ObjectSpec):
        proto_type = 'beat_track'
        proto_ext = model_registry_pb2.beat_track

        pitch = model.WrappedProtoProperty(model.Pitch)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitch_changed = core.Callback[model.PropertyChange[model.Pitch]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.BeatTrackDescription
