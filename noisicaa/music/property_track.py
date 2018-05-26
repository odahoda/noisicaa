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
from typing import Any, Optional

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import model
from . import pmodel
from . import base_track
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class SetTimeSignature(commands.Command):
    proto_type = 'set_time_signature'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetTimeSignature, pb)
        track = down_cast(pmodel.PropertyTrack, pool[self.proto.command.target])

        for measure_id in pb.measure_ids:
            measure = down_cast(pmodel.PropertyMeasure, pool[measure_id])
            assert measure.is_child_of(track)
            measure.time_signature = model.TimeSignature(pb.upper, pb.lower)

commands.Command.register_command(SetTimeSignature)


class PropertyMeasure(pmodel.PropertyMeasure, base_track.Measure):
    @property
    def empty(self) -> bool:
        return True


class PropertyTrack(pmodel.PropertyTrack, base_track.MeasuredTrack):
    measure_cls = PropertyMeasure

    def create(self, num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        for _ in range(num_measures):
            self.append_measure()

    def create_empty_measure(self, ref: Optional[pmodel.Measure]) -> PropertyMeasure:
        measure = down_cast(PropertyMeasure, super().create_empty_measure(ref))

        if ref is not None:
            ref = down_cast(PropertyMeasure, ref)
            measure.time_signature = ref.time_signature

        return measure

    def create_track_connector(self, **kwargs: Any) -> base_track.TrackConnector:
        raise RuntimeError("No track connector for PropertyTrack")
