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

from noisicaa import audioproc
from noisicaa import value_types
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2
from . import model


def update(
        track: model.BeatTrack, *, set_pitch: value_types.Pitch = None) -> music.Command:
    cmd = music.Command(command='update_beat_track')
    pb = cmd.Extensions[commands_registry_pb2.update_beat_track]
    pb.track_id = track.id
    if set_pitch is not None:
        pb.set_pitch.CopyFrom(set_pitch.to_proto())
    return cmd

def create_beat(
        measure: model.BeatMeasure, *,
        time: audioproc.MusicalTime,
        velocity: int = None
) -> music.Command:
    cmd = music.Command(command='create_beat')
    pb = cmd.Extensions[commands_registry_pb2.create_beat]
    pb.measure_id = measure.id
    pb.time.CopyFrom(time.to_proto())
    if velocity is not None:
        pb.velocity = velocity
    return cmd

def update_beat(
        beat: model.Beat, *, set_velocity: int = None) -> music.Command:
    cmd = music.Command(command='update_beat')
    pb = cmd.Extensions[commands_registry_pb2.update_beat]
    pb.beat_id = beat.id
    if set_velocity is not None:
        pb.set_velocity = set_velocity
    return cmd

def delete_beat(beat: model.Beat) -> music.Command:
    cmd = music.Command(command='delete_beat')
    pb = cmd.Extensions[commands_registry_pb2.delete_beat]
    pb.beat_id = beat.id
    return cmd
