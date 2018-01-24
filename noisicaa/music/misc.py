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

# TODO: pylint-unclean

class Pos2F(object):
    def __init__(self, x, y):
        self._x = float(x)
        self._y = float(y)

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __eq__(self, other):
        if not isinstance(other, Pos2F):
            return False

        return (self._x == other._x and self._y == other._y)

    def __add__(self, other):
        if not isinstance(other, Pos2F):
            raise TypeError(
                "Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self._x + other._x, self._y + other._y)

    def __sub__(self, other):
        if not isinstance(other, Pos2F):
            raise TypeError(
                "Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self._x - other._x, self._y - other._y)
