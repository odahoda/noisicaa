#!/usr/bin/python3

import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from . import libporttime

class PortTimeTest(unittest.TestCase):
    def testFoo(self):
        self.assertFalse(libporttime.Pt_Started())


if __name__ == '__init__':
    unittest.main()
