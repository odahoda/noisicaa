#!/usr/bin/python3

import os.path
import unittest
import glob
import tempfile
import shutil

from noisicaa.constants import DATA_DIR
from . import svg_symbol


class _FileTest(unittest.TestCase):
    def __init__(self, path):
        super().__init__('runTest')
        self.path = path

    def __str__(self):
        return "%s (%s.%s)" % (
            os.path.basename(self.path),
            self.__class__.__module__, self.__class__.__name__)

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache_dir)

    def runTest(self):
        sym = svg_symbol.SvgSymbol(
            self.path, cache_dir=self.cache_dir)
        xml = sym.get_xml()


class FileTestSuite(unittest.TestSuite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        paths = sorted(
            glob.glob(os.path.join(DATA_DIR, 'symbols', '*.svg')))
        for path in paths:
            if path.endswith('.stripped.svg'):
                continue
            self.addTest(_FileTest(path))


def load_tests(loader, tests, pattern):
    tests = filter_suite(tests)
    tests.addTest(FileTestSuite())
    return tests

def filter_suite(suite):
    filtered = unittest.TestSuite()
    for t in suite:
        if not type(t).__name__.startswith('_'):
            if isinstance(t, unittest.TestSuite):
                t = filter_suite(t)
            filtered.addTest(t)
    return filtered

if __name__ == '__main__':
    unittest.main()
