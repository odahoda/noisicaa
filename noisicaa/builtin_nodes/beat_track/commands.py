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

from noisicaa import audioproc
from noisicaa import model
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2

def set_beat_track_pitch(
        node_id: int, *, pitch: model.Pitch) -> music.Command:
    cmd = music.Command(target=node_id, command='set_beat_track_pitch')
    pb = cmd.Extensions[commands_registry_pb2.set_beat_track_pitch]  # type: ignore
    pb.pitch.CopyFrom(pitch.to_proto())
    return cmd

def set_beat_velocity(
        node_id: int, *, velocity: int) -> music.Command:
    cmd = music.Command(target=node_id, command='set_beat_velocity')
    pb = cmd.Extensions[commands_registry_pb2.set_beat_velocity]  # type: ignore
    pb.velocity = velocity
    return cmd

def add_beat(
        node_id: int, *, time: audioproc.MusicalTime) -> music.Command:
    cmd = music.Command(target=node_id, command='add_beat')
    pb = cmd.Extensions[commands_registry_pb2.add_beat]  # type: ignore
    pb.time.CopyFrom(time.to_proto())
    return cmd

def remove_beat(
        node_id: int, *, beat_id: int) -> music.Command:
    cmd = music.Command(target=node_id, command='remove_beat')
    pb = cmd.Extensions[commands_registry_pb2.remove_beat]  # type: ignore
    pb.beat_id = beat_id
    return cmd
