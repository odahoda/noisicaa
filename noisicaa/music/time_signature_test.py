#!/usr/bin/python3

import unittest

from .time_signature import TimeSignature


class TimeSignatureTest(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(TimeSignature(4, 4), TimeSignature(4, 4))
        self.assertNotEqual(TimeSignature(4, 4), TimeSignature(2, 2))

    def test_compare_with_bad_class(self):
        with self.assertRaises(TypeError):
            # pylint: disable=expression-not-assigned
            TimeSignature() == 'foo'

    def test_attributes(self):
        self.assertEqual(TimeSignature(3, 4).value, (3, 4))
        self.assertEqual(TimeSignature(3, 2).upper, 3)
        self.assertEqual(TimeSignature(3, 2).lower, 2)


if __name__ == '__main__':
    unittest.main()
