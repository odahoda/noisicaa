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

from noisicaa import audioproc
from . import proto_value


class ControlValue(proto_value.ProtoValue):
    def __init__(self, name: str, value: float, generation: int) -> None:
        self.__name = name
        self.__value = value
        self.__generation = generation

    def __str__(self) -> str:
        return '<%s %f %d>' % (self.__name, self.__value, self.__generation)
    __repr__ = __str__

    def to_proto(self) -> 'audioproc.ControlValue':
        return audioproc.ControlValue(
            name=self.__name,
            value=self.__value,
            generation=self.__generation)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'ControlValue':
        if not isinstance(pb, audioproc.ControlValue):
            raise TypeError(type(pb).__name__)
        return ControlValue(pb.name, pb.value, pb.generation)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def value(self) -> float:
        return self.__value

    @property
    def generation(self) -> int:
        return self.__generation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ControlValue):
            return False

        return (
            self.__name == other.__name
            and self.__value == other.__value
            and self.__generation == other.__generation)
