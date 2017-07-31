#!/usr/bin/python3

import builtins
import json
import pprint
import unittest

from mox3 import stubout
from pyfakefs import fake_filesystem

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa.core import fileutil
from noisicaa.core import storage
from . import project
from . import sheet


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
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        state = store_retrieve(p.serialize())
        p2 = project.Project(state=state)
        self.assertEqual(len(p2.sheets), 1)

    def test_demo(self):
        p = project.BaseProject.make_demo()
        #pprint.pprint(p.serialize())


class AddSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        cmd = project.AddSheet(name='Sheet 1')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')

    def test_duplicate_name(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        cmd = project.AddSheet(name='Sheet 1')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.id, cmd)


class DeleteSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        p.sheets.append(sheet.Sheet(name='Sheet 2'))
        cmd = project.DeleteSheet(name='Sheet 1')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 2')

    def test_last_sheet(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        p.sheets.append(sheet.Sheet(name='Sheet 2'))
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.id, cmd)
        cmd = project.DeleteSheet(name='Sheet 2')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')
        self.assertEqual(p.current_sheet, 0)


class RenameSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        cmd = project.RenameSheet(name='Sheet 1', new_name='Foo')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(p.sheets[0].name, 'Foo')

    def test_unchanged(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 1')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')

    def test_duplicate_name(self):
        p = project.BaseProject()
        p.sheets.append(sheet.Sheet(name='Sheet 1'))
        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.id, cmd)
        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 2')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.id, cmd)


class SetCurrentSheetTest(unittest.TestCase):
    def test_ok(self):
        p = project.BaseProject()
        p.add_sheet(sheet.Sheet(name='Sheet 1'))
        p.add_sheet(sheet.Sheet(name='Sheet 2'))
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.id, cmd)
        self.assertEqual(p.current_sheet, 1)


class ProjectTest(unittest.TestCase):
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

    def test_create(self):
        p = project.Project()
        p.create('/foo.noise')
        p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.noise'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f = fileutil.File('/foo.noise')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    def test_open_and_replay(self):
        p = project.Project()
        p.create('/foo.noise')
        try:
            p.dispatch_command(p.id, project.AddSheet())
            sheet_id = p.sheets[-1].id
            p.dispatch_command(sheet_id, sheet.AddTrack(
                track_type='score',
                parent_group_id=p.sheets[-1].master_group.id))
            track_id = p.sheets[-1].master_group.tracks[-1].id
        finally:
            p.close()

        p = project.Project()
        p.open('/foo.noise')
        try:
            self.assertEqual(p.sheets[-1].id, sheet_id)
            self.assertEqual(p.sheets[-1].master_group.tracks[-1].id, track_id)
        finally:
            p.close()

    def test_create_checkpoint(self):
        p = project.Project()
        p.create('/foo.emp')
        try:
            p.create_checkpoint()
        finally:
            p.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000001'))


if __name__ == '__main__':
    unittest.main()
