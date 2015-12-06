#!/usr/bin/python3

import builtins
import json
import unittest

from mox3 import stubout
import fake_filesystem

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa import fileutil
from . import project


def store_retrieve(obj):
    serialized = json.dumps(obj, cls=project.JSONEncoder)
    deserialized = json.loads(serialized, cls=project.JSONDecoder)
    return deserialized


class BaseProjectTest(unittest.TestCase):
    def test_serialize(self):
        p = project.BaseProject()
        self.assertIsInstance(p.serialize(), dict)

    def test_deserialize(self):
        p = project.BaseProject()
        state = store_retrieve(p.serialize())
        p2 = project.Project(state=state)
        self.assertEqual(len(p2.sheets), 1)


class AddSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 2)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')
        self.assertEqual(p.sheets[1].name, 'Sheet 2')

    def test_duplicate_name(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 1')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.address, cmd)


class DeleteSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.DeleteSheet(name='Sheet 1')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 2')

    def test_last_sheet(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.DeleteSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')
        self.assertEqual(p.current_sheet, 0)


class RenameSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        cmd = project.RenameSheet(name='Sheet 1', new_name='Foo')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.sheets[0].name, 'Foo')

    def test_unchanged(self):
        p = project.BaseProject()
        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 1')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')

    def test_duplicate_name(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 2')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.address, cmd)


class SetCurrentSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.current_sheet, 1)


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(project, 'os', self.fake_os)
        self.stubs.SmartSet(project.fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_create(self):
        p = project.Project()
        p.create('/foo.emp')
        p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.emp'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f = fileutil.File('/foo.emp')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    def test_open(self):
        p = project.Project()
        p.create('/foo.emp')
        try:
            p.dispatch_command('/', project.AddSheet())
        finally:
            p.close()

        p = project.Project()
        p.open('/foo.emp')
        try:
            self.assertEqual(p.path, '/foo.emp')
            self.assertEqual(p.data_dir, '/foo.data')
        finally:
            p.close()

    def test_create_checkpoint(self):
        p = project.Project()
        p.create('/foo.emp')
        try:
            p.create_checkpoint()
        finally:
            p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.data/state.2.checkpoint'))
        self.assertTrue(self.fake_os.path.isfile('/foo.data/state.2.log'))
        self.assertTrue(self.fake_os.path.isfile('/foo.data/state.latest'))

        f = fileutil.File('/foo.data/state.latest')
        file_info, state_data = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-state')
        self.assertEqual(state_data['sequence_number'], 2)
        self.assertEqual(state_data['checkpoint'], 'state.2.checkpoint')
        self.assertEqual(state_data['log'], 'state.2.log')


class ScoreEventSource(unittest.TestCase):
    def test_get_events(self):
        proj = project.BaseProject()
        sheet = project.Sheet(name='test')
        proj.sheets.append(sheet)
        track = project.ScoreTrack(name='test', num_measures=2)
        sheet.tracks.append(track)
        sheet.update_tracks()
        sheet.equalize_tracks()

        source = track.create_event_source()
        events = []
        for timepos in range(0, 100000, 4096):
            events.extend(source.get_events(timepos, timepos + 4096))

        print(events)


if __name__ == '__main__':
    unittest.main()
