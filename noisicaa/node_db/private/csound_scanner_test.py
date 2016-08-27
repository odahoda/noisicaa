#!/usr/bin/python3

import unittest

from . import csound_scanner


class CSoundScannerTest(unittest.TestCase):
    def test_load_csound_nodes(self):
        scanner = csound_scanner.CSoundScanner()
        for uri, node_description in scanner.scan():
            pass


if __name__ == '__main__':
    unittest.main()
