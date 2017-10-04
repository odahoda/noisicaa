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

import builtins
import unittest

from mox3 import stubout
from pyfakefs import fake_filesystem

from . import fileutil
from . import storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_index_management(self):
        ps = storage.ProjectStorage.create('/foo')
        try:
            self.assertFalse(ps.can_undo)
            self.assertFalse(ps.can_redo)

            ps.append_log_entry(b'bla1')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla1'))
            self.assertFalse(ps.can_redo)

            pause_evt = ps.pause()

            ps.append_log_entry(b'bla2')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla2'))
            self.assertFalse(ps.can_redo)

            ps.undo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla1'))
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(),
                (storage.ACTION_FORWARD, b'bla2'))
            ps.undo()
            self.assertFalse(ps.can_undo)
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(),
                (storage.ACTION_FORWARD, b'bla1'))

            pause_evt.set()
            ps.flush()
            ps.flush_cache(0)

            ps.redo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla1'))
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(),
                (storage.ACTION_FORWARD, b'bla2'))

            ps.flush()
            ps.flush_cache(0)
            ps.redo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla2'))
            self.assertFalse(ps.can_redo)

            ps.flush()
            ps.flush_cache(0)
            ps.append_log_entry(b'bla3')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla3'))
            self.assertFalse(ps.can_redo)

            self.assertEqual(ps.next_sequence_number, 7)

            ps.flush()

            entries = list(ps.log_history_formatter.iter_unpack(ps.log_history))
            self.assertEqual(
                entries,
                [(b'f', 0, 0, 0),
                 (b'f', 1, 0, 0),
                 (b'b', 1, 1, 0),
                 (b'b', 0, 2, 0),
                 (b'f', 0, 2, 1),
                 (b'f', 1, 2, 2),
                 (b'f', 2, 0, 0)])
        finally:
            ps.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/log.index'))
        self.assertEqual(
            self.fake_os.path.getsize('/foo.data/log.index'),
            3 * ps.log_index_formatter.size)
        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/log.history'))
        self.assertEqual(
            self.fake_os.path.getsize('/foo.data/log.history'),
            7 * ps.log_history_formatter.size)
        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/log.000000'))

    def test_undo_the_undone(self):
        ps = storage.ProjectStorage.create('/foo')
        try:
            ps.append_log_entry(b'bla1')
            ps.undo()
            ps.redo()
            ps.append_log_entry(b'bla2')
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla2'))
            ps.undo()
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla1'))
            ps.undo()
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_FORWARD, b'bla1'))
            ps.undo()
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla1'))
            ps.undo()

        finally:
            ps.close()

    def test_open(self):
        ps = storage.ProjectStorage.create('/foo')
        try:
            ps.add_checkpoint(b'blurp1')
            ps.append_log_entry(b'bla1')
            ps.undo()
            ps.add_checkpoint(b'blurp2')
            ps.append_log_entry(b'bla2')
            ps.append_log_entry(b'bla3')
            ps.undo()
            ps.undo()
            ps.redo()

        finally:
            ps.close()

        ps = storage.ProjectStorage()
        ps.open('/foo')
        try:
            self.assertEqual(ps.undo_count, 2)
            self.assertEqual(ps.redo_count, 1)
            self.assertEqual(
                ps.get_log_entry_to_undo(),
                (storage.ACTION_BACKWARD, b'bla2'))
            self.assertEqual(
                ps.get_log_entry_to_redo(),
                (storage.ACTION_FORWARD, b'bla3'))

            checkpoint_number, actions = ps.get_restore_info()
            self.assertEqual(checkpoint_number, 1)
            self.assertEqual(
                actions,
                [(storage.ACTION_FORWARD, 1),
                 (storage.ACTION_FORWARD, 2),
                 (storage.ACTION_BACKWARD, 2),
                 (storage.ACTION_BACKWARD, 1),
                 (storage.ACTION_FORWARD, 1)])

            self.assertEqual(
                ps.get_checkpoint(checkpoint_number), b'blurp2')
            self.assertEqual(ps.get_log_entry(1), b'bla2')
            self.assertEqual(ps.get_log_entry(2), b'bla3')

            ps.append_log_entry(b'bla4')
            ps.add_checkpoint(b'blurp3')

        finally:
            ps.close()

    def test_checkpoints(self):
        ps = storage.ProjectStorage.create('/foo')
        try:
            ps.add_checkpoint(b'blurp1')
            self.assertEqual(ps.logs_since_last_checkpoint, 0)
            ps.append_log_entry(b'bla1')
            self.assertEqual(ps.logs_since_last_checkpoint, 1)
            ps.undo()
            self.assertEqual(ps.logs_since_last_checkpoint, 2)
            unpause_evt = ps.pause()
            ps.add_checkpoint(b'blurp2')
            self.assertEqual(ps.logs_since_last_checkpoint, 0)

            unpause_evt.set()
            ps.flush()

            entries = list(
                ps.checkpoint_index_formatter.iter_unpack(
                    ps.checkpoint_index))
            self.assertEqual(
                entries,
                [(0, 0),
                 (2, 1)])

        finally:
            ps.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.index'))
        self.assertEqual(
            self.fake_os.path.getsize('/foo.data/checkpoint.index'),
            2 * ps.checkpoint_index_formatter.size)
        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000000'))
        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000001'))


if __name__ == '__main__':
    unittest.main()
