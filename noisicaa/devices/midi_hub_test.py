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

import threading
from unittest import mock
from typing import Dict, Iterable

from noisidev import unittest
from . import libalsa
from . import midi_events
from . import midi_hub


# TODO:
# - device disconnects and reconnects while listened to.
# - virtual clock to control event sequence.


class MockSequencer(object):
    def __init__(self):
        self._ci = libalsa.ClientInfo(10, 'test client')
        self._pi = libalsa.PortInfo(
            self._ci, 14,
            'test port', {'read'}, {'midi_generic', 'hardware'})

        self._events = {
            '10/14': [midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120)]
            }
        self._connected = {}  # type: Dict[str, Iterable[midi_events.MidiEvent]]
        self._exhausted = threading.Event()

    def close(self):
        pass

    def list_all_ports(self):
        yield self._pi

    def connect(self, port_info):
        dev = port_info.device_id
        assert dev in self._events
        assert dev not in self._connected
        self._connected[dev] = iter(self._events[dev])

    def disconnect(self, port_info):
        dev = port_info.device_id
        assert dev in self._events
        assert dev in self._connected
        del self._connected[dev]

    def get_pollin_fds(self):
        return []

    def get_event(self):
        for it in self._connected.values():
            try:
                return next(it)
            except StopIteration:
                pass

        self._exhausted.set()
        return None

    def wait_until_done(self):
        self._exhausted.wait()


class MidiHubTest(unittest.TestCase):
    def setup_testcase(self):
        self.seq = MockSequencer()

    def test_start_stop(self):
        hub = midi_hub.MidiHub(self.seq)
        hub.start()
        self.seq.wait_until_done()
        hub.stop()

    def test_stop_before_start(self):
        hub = midi_hub.MidiHub(self.seq)
        hub.stop()

    def test_list_devices(self):
        with midi_hub.MidiHub(self.seq) as hub:
            hub.list_devices()

    def test_listener(self):
        callback = mock.Mock()
        with midi_hub.MidiHub(self.seq) as hub:
            listener = hub.add_event_handler('10/14', callback)
            self.seq.wait_until_done()
            hub.remove_event_handler('10/14', listener)

        callback.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))

    def test_listen_before_start(self):
        hub = midi_hub.MidiHub(self.seq)
        with self.assertRaises(AssertionError):
            hub.add_event_handler('10/14', mock.Mock())

    def test_listener_same_device(self):
        callback1 = mock.Mock()
        callback2 = mock.Mock()
        with midi_hub.MidiHub(self.seq) as hub:
            listener1 = hub.add_event_handler('10/14', callback1)
            listener2 = hub.add_event_handler('10/14', callback2)
            self.seq.wait_until_done()
            hub.remove_event_handler('10/14', listener1)
            hub.remove_event_handler('10/14', listener2)

        callback1.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))
        callback2.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))

    def test_listener_unknown_device(self):
        with midi_hub.MidiHub(self.seq) as hub:
            with self.assertRaises(midi_hub.Error):
                hub.add_event_handler('111/222', mock.Mock())
