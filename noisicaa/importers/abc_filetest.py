#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import os.path
import glob

from noisidev import unittest
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
