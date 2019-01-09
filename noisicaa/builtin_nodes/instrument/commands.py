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

from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2

def update_instrument(
        node_id: int, *, instrument_uri: str = None) -> music.Command:
    cmd = music.Command(target=node_id, command='update_instrument')
    pb = cmd.Extensions[commands_registry_pb2.update_instrument]
    pb.instrument_uri = instrument_uri
    return cmd
