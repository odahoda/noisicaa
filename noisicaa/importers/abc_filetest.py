#!/usr/bin/python3

import logging
import os.path
import re
import pprint
import fractions
import unittest
import glob

from noisicaa import music
from . import abc


class _FileTest(unittest.TestCase):
    def __init__(self, path):
        super().__init__('runTest')
        self.path = path

    def __str__(self):
        return "%s (%s.%s)" % (
            os.path.basename(self.path),
            self.__class__.__module__, self.__class__.__name__)

    def runTest(self):
        project = music.Project()
        importer = abc.ABCImporter()
        importer.import_file(self.path, project)


class FileTestSuite(unittest.TestSuite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for path in glob.glob(os.path.join(os.path.dirname(__file__), 'testdata', '*.abc')):
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
    #logging.basicConfig(level=logging.DEBUG)

    unittest.main()
