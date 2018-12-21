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

from google.protobuf import message as protobuf

from . import project_pb2
from . import model_base


class SizeF(model_base.ProtoValue):
    def __init__(self, width: float, height: float) -> None:
        self.__width = float(width)
        self.__height = float(height)

    def to_proto(self) -> project_pb2.SizeF:
        return project_pb2.SizeF(width=self.__width, height=self.__height)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'SizeF':
        if not isinstance(pb, project_pb2.SizeF):
            raise TypeError(type(pb).__name__)
        return SizeF(pb.width, pb.height)

    @property
    def width(self) -> float:
        return self.__width

    @property
    def height(self) -> float:
        return self.__height

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SizeF):
            return False

        return self.__width == other.__width and self.__height == other.__height

    def __add__(self, other: 'SizeF') -> 'SizeF':
        if not isinstance(other, SizeF):
            raise TypeError("Expected SizeF, got %s" % type(other).__name__)

        return self.__class__(self.__width + other.__width, self.__height + other.__height)

    def __sub__(self, other: 'SizeF') -> 'SizeF':
        if not isinstance(other, SizeF):
            raise TypeError("Expected SizeF, got %s" % type(other).__name__)

        return self.__class__(self.__width - other.__width, self.__height - other.__height)
