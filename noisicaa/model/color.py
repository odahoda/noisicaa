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

import decimal
from google.protobuf import message as protobuf

from . import project_pb2
from . import model_base


class Color(model_base.ProtoValue):
    def __init__(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        self.__context = decimal.Context(prec=4)
        self.__r = self.__context.create_decimal_from_float(r)
        self.__g = self.__context.create_decimal_from_float(g)
        self.__b = self.__context.create_decimal_from_float(b)
        self.__a = self.__context.create_decimal_from_float(a)

    def to_proto(self) -> project_pb2.Color:
        return project_pb2.Color(
            r=float(self.__r), g=float(self.__g), b=float(self.__b), a=float(self.__a))

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'Color':
        if not isinstance(pb, project_pb2.Color):
            raise TypeError(type(pb).__name__)
        return Color(pb.r, pb.g, pb.b, pb.a)

    @property
    def r(self) -> float:
        return float(self.__r)

    @property
    def g(self) -> float:
        return float(self.__g)

    @property
    def b(self) -> float:
        return float(self.__b)

    @property
    def a(self) -> float:
        return float(self.__a)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return False

        return (
            self.__r == other.__r
            and self.__g == other.__g
            and self.__b == other.__b
            and self.__a == other.__a)

    def __str__(self) -> str:
        return 'Color(%s, %s, %s, %s)' % (self.__r, self.__g, self.__b, self.__a)
    __repr__ = __str__
