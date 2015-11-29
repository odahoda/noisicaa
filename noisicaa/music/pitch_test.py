#!/usr/bin/python3

import unittest

from .pitch import Pitch


class PitchTest(unittest.TestCase):
    def test_from_string(self):
        p = Pitch('G#4')
        self.assertEqual(p.name, 'G#4')
        self.assertEqual(p.octave, 4)
        self.assertEqual(p.value, 'G')
        self.assertEqual(p.accidental, '#')

    def test_equal(self):
        self.assertEqual(Pitch('G#5'), Pitch('G#5'))
        self.assertNotEqual(Pitch('G#5'), Pitch('G#4'))
        self.assertNotEqual(Pitch('G#5'), Pitch('G5'))
        self.assertNotEqual(Pitch('G#5'), Pitch('A#5'))

    def test_sort(self):
        self.assertGreater(Pitch('G#5'), Pitch('G5'))
        self.assertGreater(Pitch('A5'), Pitch('G5'))
        self.assertGreater(Pitch('C6'), Pitch('B5'))
        self.assertGreater(Pitch('G6'), Pitch('G5'))

    def test_transposed(self):
        p = Pitch('G#4')
        self.assertEqual(p.transposed(octaves=-1), Pitch('G#3'))


if __name__ == '__main__':
    unittest.main()
