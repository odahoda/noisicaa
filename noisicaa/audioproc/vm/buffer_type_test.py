#!/usr/bin/python3

import unittest

from . import buffer_type

class BufferTypeTest(unittest.TestCase):

    def test_float(self):
        bt = buffer_type.Float()

        self.assertEqual(len(bt), 4)

    def test_float_array(self):
        bt = buffer_type.FloatArray(5)

        self.assertEqual(len(bt), 20)


if __name__ == '__main__':
    unittest.main()
