#!/usr/bin/python3

import logging
import time
import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from . import midi_hub

class MidiHubTest(unittest.TestCase):
    def test_list_devices(self):
        with midi_hub.MidiHub() as hub:
            hub.list_devices()

    def test_start_stop(self):
        hub = midi_hub.MidiHub()
        hub.start()
        time.sleep(10)
        hub.stop()

    def test_listener(self):
        def callback(event):
            print("got event %s" % event)

        with midi_hub.MidiHub() as hub:
            listener = hub.listeners.add('24/0', callback)
            time.sleep(10)
            listener.remove()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
