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

from typing import Tuple

from google.protobuf import message as protobuf

from . import proto_value
from . import value_types_pb2


class TimeSignature(proto_value.ProtoValue):
    def __init__(self, upper: int = 4, lower: int = 4) -> None:
        if upper < 1 or upper > 99:
            raise ValueError("Bad time signature %r/%r" % (upper, lower))
        if lower < 1 or lower > 99:
            raise ValueError("Bad time signature %r/%r" % (upper, lower))

        self._upper = upper
        self._lower = lower

    def to_proto(self) -> value_types_pb2.TimeSignature:
        return value_types_pb2.TimeSignature(upper=self._upper, lower=self._lower)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'TimeSignature':
        if not isinstance(pb, value_types_pb2.TimeSignature):
            raise TypeError(type(pb).__name__)
        return TimeSignature(pb.upper, pb.lower)

    def __repr__(self) -> str:
        return 'TimeSignature(%d/%d)' % (self.upper, self.lower)

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False

        if not isinstance(other, TimeSignature):
            raise TypeError(
                "Can't compare %s to %s" % (type(self).__name__, type(other).__name__))

        return self.value == other.value

    @property
    def value(self) -> Tuple[int, int]:
        return (self._upper, self._lower)

    @property
    def upper(self) -> int:
        return self._upper

    @property
    def lower(self) -> int:
        return self._lower
