#!/usr/bin/python3

import unittest

from . import ladspa_scanner


class LadspaScannerTest(unittest.TestCase):
    def test_scam(self):
        scanner = ladspa_scanner.LadspaScanner()
        for uri, node_description in scanner.scan():
            pass


if __name__ == '__main__':
    unittest.main()
