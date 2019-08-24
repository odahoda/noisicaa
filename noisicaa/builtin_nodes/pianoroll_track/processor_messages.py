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

import typing

from noisicaa import audioproc
from noisicaa.builtin_nodes.pianoroll import processor_messages
from noisicaa.builtin_nodes.pianoroll import processor_messages_pb2

if typing.TYPE_CHECKING:
    from . import model


def add_segment(
        track: 'model.PianoRollTrack',
        segment: 'model.PianoRollSegment',
) -> audioproc.ProcessorMessage:
    return processor_messages.add_segment(
        track.pipeline_node_id,
        segment.id,
        segment.duration)


def remove_segment(
        track: 'model.PianoRollTrack',
        segment: 'model.PianoRollSegment',
) -> audioproc.ProcessorMessage:
    return processor_messages.remove_segment(
        track.pipeline_node_id,
        segment.id)


def update_segment(
        track: 'model.PianoRollTrack',
        segment: 'model.PianoRollSegment',
) -> audioproc.ProcessorMessage:
    return processor_messages.update_segment(
        track.pipeline_node_id,
        segment.id,
        segment.duration)


def add_segment_ref(
        track: 'model.PianoRollTrack',
        segment_ref: 'model.PianoRollSegmentRef',
) -> audioproc.ProcessorMessage:
    return processor_messages.add_segment_ref(
        track.pipeline_node_id,
        segment_ref.id,
        segment_ref.time,
        segment_ref.segment.id)


def remove_segment_ref(
        track: 'model.PianoRollTrack',
        segment_ref: 'model.PianoRollSegmentRef',
) -> audioproc.ProcessorMessage:
    return processor_messages.remove_segment_ref(
        track.pipeline_node_id,
        segment_ref.id)


def update_segment_ref(
        track: 'model.PianoRollTrack',
        segment_ref: 'model.PianoRollSegmentRef',
) -> audioproc.ProcessorMessage:
    return processor_messages.update_segment_ref(
        track.pipeline_node_id,
        segment_ref.id,
        segment_ref.time)


def add_event(
        track: 'model.PianoRollTrack',
        segment: 'model.PianoRollSegment',
        event: 'model.PianoRollEvent',
) -> audioproc.ProcessorMessage:
    return processor_messages.add_event(
        track.pipeline_node_id,
        segment.id,
        event.id,
        event.midi_event.time,
        {
            0x80: processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_OFF,
            0x90: processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_ON,
        }[event.midi_event.midi[0] & 0xf0],
        event.midi_event.midi[0] & 0x0f,
        event.midi_event.midi[1],
        event.midi_event.midi[2])


def remove_event(
        track: 'model.PianoRollTrack',
        segment: 'model.PianoRollSegment',
        event: 'model.PianoRollEvent',
) -> audioproc.ProcessorMessage:
    return processor_messages.remove_event(
        track.pipeline_node_id,
        segment.id,
        event.id)
