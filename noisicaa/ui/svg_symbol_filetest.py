#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
