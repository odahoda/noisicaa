#!/usr/bin/python3

import logging
import threading
import time
import unittest
from unittest import mock

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
        self._connected = {}
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
        else:
            self._exhausted.set()
            return None

    def wait_until_done(self):
        self._exhausted.wait()


class MidiHubTest(unittest.TestCase):
    def setUp(self):
        self.seq = MockSequencer()

    def test_start_stop(self):
        hub = midi_hub.MidiHub(self.seq)
        hub.start()
        hub._seq.wait_until_done()
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
            listener = hub.listeners.add('10/14', callback)
            hub._seq.wait_until_done()
            listener.remove()

        callback.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))

    def test_listen_before_start(self):
        hub = midi_hub.MidiHub(self.seq)
        with self.assertRaises(AssertionError):
            hub.listeners.add('10/14', mock.Mock())

    def test_listener_same_device(self):
        callback1 = mock.Mock()
        callback2 = mock.Mock()
        with midi_hub.MidiHub(self.seq) as hub:
            listener1 = hub.listeners.add('10/14', callback1)
            listener2 = hub.listeners.add('10/14', callback2)
            hub._seq.wait_until_done()
            listener1.remove()
            listener2.remove()

        callback1.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))
        callback2.assert_called_with(
            midi_events.NoteOnEvent(1000, '10/14', 0, 65, 120))

    def test_listener_unknown_device(self):
        with midi_hub.MidiHub(self.seq) as hub:
            with self.assertRaises(midi_hub.Error):
                hub.listeners.add('111/222', mock.Mock())


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
