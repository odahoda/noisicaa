#!/usr/bin/python3

import unittest

from . import lv2_scanner


class LV2ScannerTest(unittest.TestCase):
    def test_scan(self):
        scanner = lv2_scanner.LV2Scanner()
        for uri, node_description in scanner.scan():
            pass


if __name__ == '__main__':
    unittest.main()
