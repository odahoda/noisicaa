#!/usr/bin/python3

import unittest

from . import builtin_scanner
from . import preset_scanner


class PresetScannerTest(unittest.TestCase):
    def setUp(self):
        scanner = builtin_scanner.BuiltinScanner()
        self.nodes = dict(scanner.scan())

    def test_scan(self):
        scanner = preset_scanner.PresetScanner(self.nodes)
        for uri, preset_description in scanner.scan():
            print(uri)


if __name__ == '__main__':
    unittest.main()
