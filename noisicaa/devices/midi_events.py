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

class MidiEvent(object):
    NOTE_ON = 'note-on'
    NOTE_OFF = 'note-off'
    CONTROLLER_CHANGE = 'controller-change'

    def __init__(self, type, timestamp, device_id):
        self.type = type
        self.timestamp = timestamp
        self.device_id = device_id

    def __eq__(self, other):
        return (self.type, self.timestamp, self.device_id) == (other.type, other.timestamp, other.device_id)


class NoteOnEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, note, velocity):
        super().__init__(MidiEvent.NOTE_ON, timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOnEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.note, self.velocity) == (other.channel, other.note, other.velocity)


class NoteOffEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, note, velocity):
        super().__init__(MidiEvent.NOTE_OFF, timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOffEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.note, self.velocity) == (other.channel, other.note, other.velocity)


class ControlChangeEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, controller, value):
        super().__init__(MidiEvent.CONTROLLER_CHANGE, timestamp, device_id)
        self.channel = channel
        self.controller = controller
        self.value = value

    def __str__(self):
        return '<%d ControlChangeEvent %d %d %d>' % (
            self.timestamp, self.channel, self.controller, self.value)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.controller, self.value) == (other.channel, other.controller, other.value)


class DeviceChangeEvent(MidiEvent):
    def __init__(self, timestamp, device_id, evt, client_id, port_id):
        super().__init__(evt, timestamp, device_id)
        self.evt = evt
        self.client_id = client_id
        self.port_id = port_id

    def __str__(self):
        return '<%d DeviceChangeEvent %s %d %d>' % (
            self.timestamp, self.evt, self.client_id, self.port_id)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.evt, self.client_id, self.port_id) == (other.evt, other.client_id, other.port_id)
