#!/usr/bin/python3

import builtins
import unittest

from mox3 import stubout
from pyfakefs import fake_filesystem

from noisicaa.core import fileutil
from . import project_storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(project_storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_index_management(self):
        ps = project_storage.ProjectStorage.create('/foo')
        try:
            self.assertFalse(ps.can_undo)
            self.assertFalse(ps.can_redo)

            ps.append_log_entry(b'bla1')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla1')
            self.assertFalse(ps.can_redo)

            pause_evt = ps.pause()

            ps.append_log_entry(b'bla2')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla2')
            self.assertFalse(ps.can_redo)

            ps.undo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla1')
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(), b'bla2')
            ps.undo()
            self.assertFalse(ps.can_undo)
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(), b'bla1')

            pause_evt.set()
            ps.flush()
            ps.flush_cache(0)

            ps.redo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla1')
            self.assertTrue(ps.can_redo)
            self.assertEqual(
                ps.get_log_entry_to_redo(), b'bla2')

            ps.flush()
            ps.flush_cache(0)
            ps.redo()
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla2')
            self.assertFalse(ps.can_redo)

            ps.flush()
            ps.flush_cache(0)
            ps.append_log_entry(b'bla3')
            self.assertTrue(ps.can_undo)
            self.assertEqual(
                ps.get_log_entry_to_undo(), b'bla3')
            self.assertFalse(ps.can_redo)

            self.assertEqual(ps.next_sequence_number, 7)

            ps.flush()

            entries = list(ps.log_history_formatter.iter_unpack(ps.log_history))
            self.assertEqual(
                entries,
                [(b'e', 0, 0, 0),
                 (b'e', 1, 0, 0),
                 (b'u', 1, 1, 0),
                 (b'u', 0, 2, 0),
                 (b'r', 0, 2, 1),
                 (b'r', 1, 2, 2),
                 (b'e', 2, 0, 0)])
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

    def test_open(self):
        ps = project_storage.ProjectStorage.create('/foo')
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

        ps = project_storage.ProjectStorage()
        ps.open('/foo')
        try:
            self.assertEqual(ps.undo_count, 2)
            self.assertEqual(ps.redo_count, 1)
            self.assertEqual(ps.get_log_entry_to_undo(), b'bla2')
            self.assertEqual(ps.get_log_entry_to_redo(), b'bla3')

            checkpoint_number, actions = ps.get_restore_info()
            self.assertEqual(checkpoint_number, 1)
            self.assertEqual(
                actions,
                [(ps.ACTION_LOG_ENTRY, 1),
                 (ps.ACTION_LOG_ENTRY, 2),
                 (ps.ACTION_UNDO, 2),
                 (ps.ACTION_UNDO, 1),
                 (ps.ACTION_REDO, 1)])

            self.assertEqual(
                ps.get_checkpoint(checkpoint_number), b'blurp2')
            self.assertEqual(ps.get_log_entry(1), b'bla2')
            self.assertEqual(ps.get_log_entry(2), b'bla3')

            ps.append_log_entry(b'bla4')
            ps.add_checkpoint(b'blurp3')

        finally:
            ps.close()

    def test_checkpoints(self):
        ps = project_storage.ProjectStorage.create('/foo')
        try:
            ps.add_checkpoint(b'blurp1')
            ps.append_log_entry(b'bla1')
            ps.undo()
            ps.add_checkpoint(b'blurp2')
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

    # def test_create(self):
    #     p = project.Project()
    #     p.create('/foo.emp')
    #     p.close()

    #     self.assertTrue(self.fake_os.path.isfile('/foo.emp'))
    #     self.assertTrue(self.fake_os.path.isdir('/foo.data'))

    #     f = fileutil.File('/foo.emp')
    #     file_info, contents = f.read_json()
    #     self.assertEqual(file_info.version, 1)
    #     self.assertEqual(file_info.filetype, 'project-header')
    #     self.assertIsInstance(contents, dict)

    # def test_open_and_replay(self):
    #     p = project.Project()
    #     p.create('/foo.emp')
    #     try:
    #         p.dispatch_command(p.id, project.AddSheet())
    #         sheet_id = p.sheets[-1].id
    #         p.dispatch_command(sheet_id, project.AddTrack('score'))
    #         track_id = p.sheets[-1].tracks[-1].id
    #     finally:
    #         p.close()

    #     p = project.Project()
    #     p.open('/foo.emp')
    #     try:
    #         self.assertEqual(p.sheets[-1].id, sheet_id)
    #         self.assertEqual(p.sheets[-1].tracks[-1].id, track_id)
    #         self.assertEqual(p.path, '/foo.emp')
    #         self.assertEqual(p.data_dir, '/foo.data')
    #     finally:
    #         p.close()

    # def test_create_checkpoint(self):
    #     p = project.Project()
    #     p.create('/foo.emp')
    #     try:
    #         p.create_checkpoint()
    #     finally:
    #         p.close()

    #     self.assertTrue(self.fake_os.path.isfile('/foo.data/state.2.checkpoint'))
    #     self.assertTrue(self.fake_os.path.isfile('/foo.data/state.2.log'))
    #     self.assertTrue(self.fake_os.path.isfile('/foo.data/state.latest'))

    #     f = fileutil.File('/foo.data/state.latest')
    #     file_info, state_data = f.read_json()
    #     self.assertEqual(file_info.version, 1)
    #     self.assertEqual(file_info.filetype, 'project-state')
    #     self.assertEqual(state_data['sequence_number'], 2)
    #     self.assertEqual(state_data['checkpoint'], 'state.2.checkpoint')
    #     self.assertEqual(state_data['log'], 'state.2.log')


if __name__ == '__main__':
    unittest.main()
