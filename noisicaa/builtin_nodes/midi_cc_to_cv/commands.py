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

from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2
from . import model_pb2
from . import model


def update(
        node: model.MidiCCtoCV,
) -> music.Command:
    cmd = music.Command(command='update_midi_cc_to_cv')
    pb = cmd.Extensions[commands_registry_pb2.update_midi_cc_to_cv]
    pb.node_id = node.id
    return cmd


def create_channel(
        node: model.MidiCCtoCV,
        index: int = None,
) -> music.Command:
    cmd = music.Command(command='create_midi_cc_to_cv_channel')
    pb = cmd.Extensions[commands_registry_pb2.create_midi_cc_to_cv_channel]
    pb.node_id = node.id
    if index is not None:
        pb.index = index
    return cmd


def update_channel(
        channel: model.MidiCCtoCVChannel,
        set_type: model_pb2.MidiCCtoCVChannel.Type = None,
        set_midi_channel: int = None,
        set_midi_controller: int = None,
        set_min_value: float = None,
        set_max_value: float = None,
        set_log_scale: bool = None,
) -> music.Command:
    cmd = music.Command(command='update_midi_cc_to_cv_channel')
    pb = cmd.Extensions[commands_registry_pb2.update_midi_cc_to_cv_channel]
    pb.channel_id = channel.id
    if set_type is not None:
        pb.set_type = set_type
    if set_midi_channel is not None:
        pb.set_midi_channel = set_midi_channel
    if set_midi_controller is not None:
        pb.set_midi_controller = set_midi_controller
    if set_min_value is not None:
        pb.set_min_value = set_min_value
    if set_max_value is not None:
        pb.set_max_value = set_max_value
    if set_log_scale is not None:
        pb.set_log_scale = set_log_scale
    return cmd


def delete_channel(
        channel: model.MidiCCtoCVChannel,
) -> music.Command:
    cmd = music.Command(command='delete_midi_cc_to_cv_channel')
    pb = cmd.Extensions[commands_registry_pb2.delete_midi_cc_to_cv_channel]
    pb.channel_id = channel.id
    return cmd
