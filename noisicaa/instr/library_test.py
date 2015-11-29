#!/usr/bin/python3

import json
import unittest

from .library import InstrumentLibrary


class LibraryTest(unittest.TestCase):
    def testAddSoundFont(self):
        lib = InstrumentLibrary(add_default_instruments=False)
        lib.add_soundfont('/usr/share/sounds/sf2/TimGM6mb.sf2')
        state = json.loads(json.dumps(lib.serialize()))
        lib2 = InstrumentLibrary(state=state)
        lib2.init_references()

    def testAddSample(self):
        path = '/storage/home/share/samples/ST-01/MonsterBass.wav'

        lib = InstrumentLibrary(add_default_instruments=False)
        lib.add_sample(path)
        self.assertEqual(len(lib.instruments), 1)
        self.assertEqual(lib.instruments[0].name, 'MonsterBass')
        self.assertEqual(lib.instruments[0].path, path)

        state = json.loads(json.dumps(lib.serialize()))
        lib = InstrumentLibrary(state=state)
        lib.init_references()
        self.assertEqual(len(lib.instruments), 1)
        self.assertEqual(lib.instruments[0].name, 'MonsterBass')
        self.assertEqual(lib.instruments[0].path, path)

if __name__ == '__main__':
    unittest.main()
