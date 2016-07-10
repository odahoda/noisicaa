#!/usr/bin/python3

import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from . import csound


class CSoundTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(csound.__version__, '6.07.0')

    def test_constructor(self):
        csnd = csound.CSound()

        csnd.close()

if __name__ == '__main__':
    unittest.main()
