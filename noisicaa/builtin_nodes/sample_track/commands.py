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
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2
from . import model


def create_sample(
        track: model.SampleTrack, *, time: audioproc.MusicalTime, path: str) -> music.Command:
    cmd = music.Command(command='create_sample')
    pb = cmd.Extensions[commands_registry_pb2.create_sample]
    pb.track_id = track.id
    pb.time.CopyFrom(time.to_proto())
    pb.path = path
    return cmd

def update_sample(
        sample: model.SampleRef, set_time: audioproc.MusicalTime
) -> music.Command:
    cmd = music.Command(command='update_sample')
    pb = cmd.Extensions[commands_registry_pb2.update_sample]
    pb.sample_id = sample.id
    if set_time is not None:
        pb.set_time.CopyFrom(set_time.to_proto())
    return cmd

def delete_sample(
        sample: model.SampleRef) -> music.Command:
    cmd = music.Command(command='delete_sample')
    pb = cmd.Extensions[commands_registry_pb2.delete_sample]
    pb.sample_id = sample.id
    return cmd
