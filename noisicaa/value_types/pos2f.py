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

from google.protobuf import message as protobuf

from . import proto_value
from . import value_types_pb2


class Pos2F(proto_value.ProtoValue):
    def __init__(self, x: float, y: float) -> None:
        self.__x = float(x)
        self.__y = float(y)

    def to_proto(self) -> value_types_pb2.Pos2F:
        return value_types_pb2.Pos2F(x=self.__x, y=self.__y)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'Pos2F':
        if not isinstance(pb, value_types_pb2.Pos2F):
            raise TypeError(type(pb).__name__)
        return Pos2F(pb.x, pb.y)

    @property
    def x(self) -> float:
        return self.__x

    @property
    def y(self) -> float:
        return self.__y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pos2F):
            return False

        return self.__x == other.__x and self.__y == other.__y

    def __add__(self, other: 'Pos2F') -> 'Pos2F':
        if not isinstance(other, Pos2F):
            raise TypeError("Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self.__x + other.__x, self.__y + other.__y)

    def __sub__(self, other: 'Pos2F') -> 'Pos2F':
        if not isinstance(other, Pos2F):
            raise TypeError("Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self.__x - other.__x, self.__y - other.__y)
