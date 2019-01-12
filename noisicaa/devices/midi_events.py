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

from typing import Any


class MidiEvent(object):
    NOTE_ON = 'note-on'
    NOTE_OFF = 'note-off'
    CONTROLLER_CHANGE = 'controller-change'

    def __init__(self, type: str, timestamp: int, device_id: str) -> None:  # pylint: disable=redefined-builtin
        self.type = type
        self.timestamp = timestamp
        self.device_id = device_id

    def __eq__(self, other: Any) -> bool:
        return(
            isinstance(other, MidiEvent)
            and self.type == other.type
            and self.timestamp == other.timestamp
            and self.device_id == other.device_id)


class NoteOnEvent(MidiEvent):
    def __init__(
            self, timestamp: int, device_id: str, channel: int, note: int, velocity: int) -> None:
        super().__init__(MidiEvent.NOTE_ON, timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self) -> str:
        return '<%d NoteOnEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, NoteOnEvent)
            and super().__eq__(other)
            and self.channel == other.channel
            and self.note == other.note
            and self.velocity == other.velocity)


class NoteOffEvent(MidiEvent):
    def __init__(
            self, timestamp: int, device_id: str, channel: int, note: int, velocity: int) -> None:
        super().__init__(MidiEvent.NOTE_OFF, timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self) -> str:
        return '<%d NoteOffEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, NoteOffEvent)
            and super().__eq__(other)
            and self.channel == other.channel
            and self.note == other.note
            and self.velocity == other.velocity)


class ControlChangeEvent(MidiEvent):
    def __init__(
            self, timestamp: int, device_id: str, channel: int, controller: int, value: int
    ) -> None:
        super().__init__(MidiEvent.CONTROLLER_CHANGE, timestamp, device_id)
        self.channel = channel
        self.controller = controller
        self.value = value

    def __str__(self) -> str:
        return '<%d ControlChangeEvent %d %d %d>' % (
            self.timestamp, self.channel, self.controller, self.value)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, ControlChangeEvent)
            and super().__eq__(other)
            and self.channel == other.channel
            and self.controller == other.controller
            and self.value == other.value)


class DeviceChangeEvent(MidiEvent):
    def __init__(
            self, timestamp: int, device_id: str, evt: str, client_id: int, port_id: int) -> None:
        super().__init__(evt, timestamp, device_id)
        self.evt = evt
        self.client_id = client_id
        self.port_id = port_id

    def __str__(self) -> str:
        return '<%d DeviceChangeEvent %s %d %d>' % (
            self.timestamp, self.evt, self.client_id, self.port_id)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, DeviceChangeEvent)
            and super().__eq__(other)
            and self.evt == other.evt
            and self.client_id == other.client_id
            and self.port_id == other.port_id)
