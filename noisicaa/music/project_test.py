#!/usr/bin/python3

import builtins
import json
import unittest
import textwrap

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


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(project, 'os', self.fake_os)
        self.stubs.SmartSet(project.fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def tearDown(self):
        self.stubs.SmartUnsetAll()

    def testCreate(self):
        p = project.Project()
        p.create('/foo.emp')
        self.assertTrue(self.fake_os.path.isfile('/foo.emp'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f =  fileutil.File('/foo.emp')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    def testOpen(self):
        contents = textwrap.dedent("""\
            NOISICAA
            Version: 1
            File-Type: project-header
            Content-Type: application/json; charset="utf-8"

            {"data_dir": "foo.data"}""").encode('ascii')
        self.fs.CreateFile('/foo.emp', contents=contents)
        self.fs.CreateDirectory('/foo.data')

        p = project.Project()
        p.open('/foo.emp')
        self.assertEqual(p.path, '/foo.emp')
        self.assertEqual(p.data_dir, '/foo.data')

    def testSerialize(self):
        p = project.Project()
        self.assertIsInstance(p.serialize(), dict)

    def testDeserialize(self):
        p = project.Project()
        state = store_retrieve(p.serialize())
        p2 = project.Project(state=state)
        self.assertEqual(len(p2.sheets), 1)

    def testWriteCheckpoint(self):
        p = project.Project()
        p.create('/foo.emp')
        path = p.write_checkpoint()

        f = fileutil.File(path)
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-checkpoint')
        self.assertIsInstance(contents, dict)

    def testAddSheet(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 2)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')
        self.assertEqual(p.sheets[1].name, 'Sheet 2')

    def testAddSheetDuplicateName(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 1')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.address, cmd)

    def testDeleteSheet(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.DeleteSheet(name='Sheet 1')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 2')

    def testDeleteSheetLastSheet(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.DeleteSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(len(p.sheets), 1)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')
        self.assertEqual(p.current_sheet, 0)

    def testRenameSheet(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.RenameSheet(name='Sheet 1', new_name='Foo')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.sheets[0].name, 'Foo')

    def testRenameSheetUnchanged(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 1')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.sheets[0].name, 'Sheet 1')

    def testRenameSheetDuplicateName(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.RenameSheet(name='Sheet 1', new_name='Sheet 2')
        with self.assertRaises(ValueError):
            p.dispatch_command(p.address, cmd)

    def testSetCurrentSheet(self):
        p = project.Project()
        p.create('/foo.emp')

        cmd = project.AddSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        cmd = project.SetCurrentSheet(name='Sheet 2')
        p.dispatch_command(p.address, cmd)
        self.assertEqual(p.current_sheet, 1)


class ScoreEventSource(unittest.TestCase):
    def test_get_events(self):
        proj = project.Project()
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
