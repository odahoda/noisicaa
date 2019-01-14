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
from noisicaa.builtin_nodes import processor_message_registry_pb2

def update(
        node_id: str, device_uri: str = None, channel_filter: int = None
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.midi_source_update]
    if device_uri is not None:
        pb.device_uri = device_uri
    if channel_filter is not None:
        pb.channel_filter = channel_filter
    return msg

def event(node_id: str, midi: bytes) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.midi_source_event]
    pb.midi = midi
    return msg

def note_on_event(
        node_id: str, channel: int, note: int, velocity: int) -> audioproc.ProcessorMessage:
    return event(node_id, bytes([0x90 | channel, note, velocity]))

def note_off_event(node_id: str, channel: int, note: int) -> audioproc.ProcessorMessage:
    return event(node_id, bytes([0x80 | channel, note, 0]))
