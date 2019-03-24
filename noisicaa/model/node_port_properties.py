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
from . import model_base


class NodePortProperties(model_base.ProtoValue):
    def __init__(self, name: str, *, exposed: bool = False) -> None:
        self.__name = name
        self.__exposed = exposed

    def __str__(self) -> str:
        return '<%s exposed=%s>' % (self.__name, self.__exposed)
    __repr__ = __str__

    def to_proto(self) -> audioproc.NodePortProperties:
        return audioproc.NodePortProperties(
            name=self.__name,
            exposed=self.__exposed)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'NodePortProperties':
        if not isinstance(pb, audioproc.NodePortProperties):
            raise TypeError(type(pb).__name__)
        return NodePortProperties(
            name=pb.name,
            exposed=pb.exposed)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def exposed(self) -> bool:
        return self.__exposed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NodePortProperties):
            return False

        return (
            self.__name == other.__name
            and self.__exposed == other.__exposed)
