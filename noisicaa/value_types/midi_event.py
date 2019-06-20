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


class MidiEvent(proto_value.ProtoValue):
    def __init__(self, time: 'audioproc.MusicalTime', midi: bytes) -> None:
        self.__time = time
        self.__midi = midi

        self.__sortkey = (self.__time, self.__midi[0] & 0xf0, self.__midi)

    def __str__(self) -> str:
        return '<MidiEvent %.3f [%s]>' % (self.__time.to_float(), ' '.join('%02x' % m for m in self.__midi))
    __repr__ = __str__

    def to_proto(self) -> 'audioproc.MidiEvent':
        return audioproc.MidiEvent(
            time=self.__time.to_proto(),
            midi=self.__midi)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'MidiEvent':
        if not isinstance(pb, audioproc.MidiEvent):
            raise TypeError(type(pb).__name__)
        return MidiEvent(
            time=audioproc.MusicalTime.from_proto(pb.time),
            midi=pb.midi)

    @property
    def time(self) -> 'audioproc.MusicalTime':
        return self.__time

    @property
    def midi(self) -> bytes:
        return self.__midi

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return (
            self.__time == other.__time
            and self.__midi == other.__midi)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return (
            self.__time != other.__time
            or self.__midi != other.__midi)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return self.__sortkey > other.__sortkey

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return self.__sortkey >= other.__sortkey

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return self.__sortkey < other.__sortkey

    def __le__(self, other: object) -> bool:
        if not isinstance(other, MidiEvent):
            return NotImplemented
        return self.__sortkey <= other.__sortkey
