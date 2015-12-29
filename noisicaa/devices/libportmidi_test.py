#!/usr/bin/python3

import time
import unittest

import alsaseq

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from . import libportmidi

class PortMidiTest(unittest.TestCase):
    def setUp(self):
        self.test_output = alsaseq.client('test', 1, 0, True)
        alsaseq.start()

    def tearDown(self):
        alsaseq.stop()

    def test_list_devices(self):
        devices = libportmidi.list_devices()
        print('\n'.join(str(d) for d in devices))

    def test_open(self):
        dev = libportmidi.open(3, 'r')
        dev.close()

    def test_read(self):
        dev = libportmidi.open(3, 'r')
        try:
            cnt = 0
            while cnt < 10:
                event = next(dev)
                if event is not None:
                    cnt += 1
                    print(event)

        finally:
            dev.close()

    def test_write(self):
        dev = libportmidi.open(8, 'w')
        try:
            dev.write(libportmidi.NoteOnEvent(0, 0, 69, 127))
            time.sleep(0.5)
            dev.write(libportmidi.NoteOnEvent(0, 0, 71, 127))
            time.sleep(0.5)
            dev.write(libportmidi.NoteOnEvent(0, 0, 73, 127))
            time.sleep(0.5)

        finally:
            dev.close()

    def test_passthrough(self):
        out_dev = libportmidi.open(8, 'w')
        try:
            in_dev = libportmidi.open(3, 'r')
            try:
                cnt = 0
                while cnt < 100:
                    event = next(in_dev)
                    if event is not None:
                        cnt += 1
                        print(event)
                        out_dev.write(event)
            finally:
                in_dev.close()

        finally:
            out_dev.close()

if __name__ == '__main__':
    unittest.main()
