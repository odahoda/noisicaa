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

import fractions

from noisicaa import audioproc
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2

def add_sample(
        node_id: int, *, time: audioproc.MusicalTime, path: str) -> music.Command:
    cmd = music.Command(target=node_id, command='add_sample')
    pb = cmd.Extensions[commands_registry_pb2.add_sample]
    pb.time.CopyFrom(time.to_proto())
    pb.path = path
    return cmd

def remove_sample(
        node_id: int, *, sample_id: int) -> music.Command:
    cmd = music.Command(target=node_id, command='remove_sample')
    pb = cmd.Extensions[commands_registry_pb2.remove_sample]
    pb.sample_id = sample_id
    return cmd

def move_sample(
        node_id: int, *, sample_id: int, time: audioproc.MusicalTime
) -> music.Command:
    cmd = music.Command(target=node_id, command='move_sample')
    pb = cmd.Extensions[commands_registry_pb2.move_sample]
    pb.sample_id = sample_id
    pb.time.CopyFrom(time.to_proto())
    return cmd

def render_sample(
        sample_id: int, *, scale_x: fractions.Fraction
) -> music.Command:
    cmd = music.Command(target=sample_id, command='render_sample')
    pb = cmd.Extensions[commands_registry_pb2.render_sample]
    pb.scale_x.numerator = scale_x.numerator
    pb.scale_x.denominator = scale_x.denominator
    return cmd
