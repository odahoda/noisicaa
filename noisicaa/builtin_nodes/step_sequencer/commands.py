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
        node: model.StepSequencer,
        set_num_steps: int = None,
        set_time_synched: bool = None,
        add_channel: int = None,
) -> music.Command:
    cmd = music.Command(command='update_step_sequencer')
    pb = cmd.Extensions[commands_registry_pb2.update_step_sequencer]
    pb.node_id = node.id
    if set_time_synched is not None:
        pb.set_time_synched = set_time_synched
    if set_num_steps is not None:
        pb.set_num_steps = set_num_steps
    if add_channel is not None:
        pb.add_channel = add_channel
    return cmd


def update_channel(
        channel: model.StepSequencerChannel,
        set_type: model_pb2.StepSequencerChannel.Type = None,
        set_min_value: float = None,
        set_max_value: float = None,
        set_log_scale: bool = None,
) -> music.Command:
    cmd = music.Command(command='update_step_sequencer_channel')
    pb = cmd.Extensions[commands_registry_pb2.update_step_sequencer_channel]
    pb.channel_id = channel.id
    if set_type is not None:
        pb.set_type = set_type
    if set_min_value is not None:
        pb.set_min_value = set_min_value
    if set_max_value is not None:
        pb.set_max_value = set_max_value
    if set_log_scale is not None:
        pb.set_log_scale = set_log_scale
    return cmd


def delete_channel(
        channel: model.StepSequencerChannel,
) -> music.Command:
    cmd = music.Command(command='delete_step_sequencer_channel')
    pb = cmd.Extensions[commands_registry_pb2.delete_step_sequencer_channel]
    pb.channel_id = channel.id
    return cmd


def update_step(
        step: model.StepSequencerStep,
        set_enabled: bool = None,
        set_value: float = None,
) -> music.Command:
    cmd = music.Command(command='update_step_sequencer_step')
    pb = cmd.Extensions[commands_registry_pb2.update_step_sequencer_step]
    pb.step_id = step.id
    if set_enabled is not None:
        pb.set_enabled = set_enabled
    if set_value is not None:
        pb.set_value = set_value
    return cmd
