#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import builtins

from mox3 import stubout
from pyfakefs import fake_filesystem

from noisidev import unittest
from . import recordfile


class RecordFileTest(unittest.TestCase):
    def setup_testcase(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fake_fs = fake_filesystem.FakeFilesystem()
        self.fake_open = fake_filesystem.FakeFileOpen(self.fake_fs)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            recordfile.RecordFile('/test.rec', 'lala')

    def test_append_record_data_type(self):
        with recordfile.RecordFile('/test.rec', recordfile.MODE_CREATE) as r:
            r.append_record(b'lalila')
            with self.assertRaises(AssertionError):
                r.append_record('lalila')  # type: ignore[arg-type]

    def test_append_record_prop_type(self):
        with recordfile.RecordFile('/test.rec', recordfile.MODE_CREATE) as r:
            r.append_record(b'lalila', foo='bar', foo2boo='12.2')
            with self.assertRaises(AssertionError):
                r.append_record(b'lalila', foo=1)  # type: ignore[arg-type]
            with self.assertRaises(AssertionError):
                r.append_record(b'lalila', foo='1 2 3')
            with self.assertRaises(AssertionError):
                r.append_record(b'lalila', **{'foo 1': 'foo'})

    def test_append_record(self):
        with recordfile.RecordFile('/test.rec', recordfile.MODE_CREATE) as r:
            r.append_record(b'lalila', foo='a1', bar='b1')
            r.append_record(b'lumlidum\n', foo='a2')
            r.append_record(b'dubdidu\n', bar='b2')
            self.assertEqual(r.num_records, 3)

    def test_read_record(self):
        with recordfile.RecordFile('/test.rec', recordfile.MODE_CREATE) as r:
            r.append_record(b'tralala\n', foo='a')
            r.append_record(b'lulilo', bar='b')

        with recordfile.RecordFile('/test.rec', recordfile.MODE_READONLY) as r:
            data, props = r.read_record()
            self.assertEqual(data, b'tralala\n')
            self.assertEqual(props, {'foo': 'a', 'index': 0})

            data, props = r.read_record()
            self.assertEqual(data, b'lulilo')
            self.assertEqual(props, {'bar': 'b', 'index': 1})

            with self.assertRaises(EOFError):
                r.read_record()

    def test_escape_marker(self):
        with recordfile.RecordFile('/test.rec', recordfile.MODE_CREATE) as r:
            r.append_record(b'#~tralala')

        contents = self.fake_open('/test.rec', 'rb').read()
        self.assertEqual(contents.count(b'#~'), 1)

        with recordfile.RecordFile('/test.rec', recordfile.MODE_READONLY) as r:
            data, _ = r.read_record()
            self.assertEqual(data, b'#~tralala')
