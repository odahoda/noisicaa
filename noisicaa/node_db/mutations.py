#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

class Mutation(object):
    pass


class AddNodeDescription(Mutation):
    def __init__(self, uri, description):
        self.uri = uri
        self.description = description

    def __str__(self):
        return '<AddNodeDescription uri="%s">' % self.uri


class RemoveNodeDescription(Mutation):
    def __init__(self, uri):
        self.uri = uri

    def __str__(self):
        return '<RemoveNodeDescription uri="%s">' % self.uri


