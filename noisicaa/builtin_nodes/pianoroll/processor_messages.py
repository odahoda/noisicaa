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

from typing import Iterable

from noisicaa import audioproc
from noisicaa.builtin_nodes import processor_message_registry_pb2
from . import processor_messages_pb2


def emit_events(node_id: str, midi: Iterable[bytes]) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_emit_events]
    pb.midi.extend(midi)
    return msg

def note_on_event(
        node_id: str, channel: int, note: int, velocity: int) -> audioproc.ProcessorMessage:
    return emit_events(node_id, [bytes([0x90 | channel, note, velocity])])

def note_off_event(node_id: str, channel: int, note: int) -> audioproc.ProcessorMessage:
    return emit_events(node_id, [bytes([0x80 | channel, note, 0])])


def add_interval(
        node_id: str,
        id: int,  # pylint: disable=redefined-builtin
        start_time: audioproc.MusicalTime,
        end_time: audioproc.MusicalTime,
        pitch: int,
        velocity: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_add_interval]
    pb.id = id
    pb.start_time.CopyFrom(start_time.to_proto())
    pb.end_time.CopyFrom(end_time.to_proto())
    pb.pitch = pitch
    pb.velocity = velocity
    return msg


def remove_interval(
        node_id: str,
        id: int  # pylint: disable=redefined-builtin
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_remove_interval]
    pb.id = id
    return msg


def add_segment(
        node_id: str,
        segment_id: int,
        duration: audioproc.MusicalDuration,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].add_segment
    pb.id = segment_id
    pb.duration.CopyFrom(duration.to_proto())
    return msg


def remove_segment(
        node_id: str,
        segment_id: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].remove_segment
    pb.id = segment_id
    return msg


def update_segment(
        node_id: str,
        segment_id: int,
        duration: audioproc.MusicalDuration = None,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].update_segment
    pb.id = segment_id
    if duration is not None:
        pb.duration.CopyFrom(duration.to_proto())
    return msg


def add_segment_ref(
        node_id: str,
        segment_ref_id: int,
        time: audioproc.MusicalTime,
        segment_id: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].add_segment_ref
    pb.id = segment_ref_id
    pb.time.CopyFrom(time.to_proto())
    pb.segment_id = segment_id
    return msg


def remove_segment_ref(
        node_id: str,
        segment_ref_id: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].remove_segment_ref
    pb.id = segment_ref_id
    return msg


def update_segment_ref(
        node_id: str,
        segment_ref_id: int,
        time: audioproc.MusicalTime = None,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].update_segment_ref
    pb.id = segment_ref_id
    if time is not None:
        pb.time.CopyFrom(time.to_proto())
    return msg


def add_event(
        node_id: str,
        segment_id: int,
        event_id: int,
        time: audioproc.MusicalTime,
        type: processor_messages_pb2.PianoRollMutation.AddEvent.Type,  # pylint: disable=redefined-builtin
        channel: int,
        pitch: int,
        velocity: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].add_event
    pb.segment_id = segment_id
    pb.id = event_id
    pb.time.CopyFrom(time.to_proto())
    pb.type = type
    pb.channel = channel
    pb.pitch = pitch
    pb.velocity = velocity
    return msg


def remove_event(
        node_id: str,
        segment_id: int,
        event_id: int,
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation].remove_event
    pb.segment_id = segment_id
    pb.id = event_id
    return msg
