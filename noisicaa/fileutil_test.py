#!/usr/bin/python3

import builtins
import unittest
import textwrap

from mox3 import stubout
import fake_filesystem

from . import fileutil

class FileTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fake_fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fake_fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fake_fs)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def testWriteJson(self):
        fp = fileutil.File('/foo')
        fp.write_json(
            {'a': [0, 1, 2]},
            fileutil.FileInfo(filetype='test', version=1))
        self.assertTrue(self.fake_os.path.exists('/foo'))

    def testRead(self):
        contents = textwrap.dedent("""\
            NOISICAA
            Version: 1
            File-Type: test
            Checksum: a6df13cacabe3782f0fb701806ead446; type="md5"
            Content-Type: application/json; charset="utf-8"
            Content-Length: 16

            {"a": [0, 1, 2]}""").encode('ascii')
        self.fake_fs.CreateFile('/foo', contents=contents)

        fp = fileutil.File('/foo')
        header, content = fp.read()
        self.assertEqual(header.version, 1)
        self.assertEqual(header.filetype, 'test')
        self.assertEqual(header.content_type, 'application/json')
        self.assertEqual(header.encoding, 'utf-8')
        self.assertEqual(content, b'{"a": [0, 1, 2]}')

    def testReadJson(self):
        contents = textwrap.dedent("""\
            NOISICAA
            Version: 1
            File-Type: test
            Checksum: a6df13cacabe3782f0fb701806ead446; type="md5"
            Content-Type: application/json; charset="utf-8"
            Content-Length: 16

            {"a": [0, 1, 2]}""").encode('ascii')
        self.fake_fs.CreateFile('/foo', contents=contents)

        fp = fileutil.File('/foo')
        header, content = fp.read_json()
        self.assertEqual(header.version, 1)
        self.assertEqual(header.filetype, 'test')
        self.assertEqual(content, {'a': [0, 1, 2]})


class LogFileTest(unittest.TestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fake_fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fake_fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fake_fs)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            fileutil.LogFile('/test.log', 'p')

    def test_invalid_append(self):
        with fileutil.LogFile('/test.log', 'w') as fp:
            with self.assertRaises(TypeError):
                fp.append('12345678', b'L')

            with self.assertRaises(TypeError):
                fp.append(b'12345678', 'L')

            with self.assertRaises(ValueError):
                fp.append(b'12345678', b'LA')

    def test_append(self):
        fp = fileutil.LogFile('/test.log', 'w')
        try:
            fp.append(b'12345678', b'L')
        finally:
            fp.close()

        self.assertTrue(self.fake_os.path.exists('/test.log'))
        self.assertEqual(
            self.fake_open('/test.log', 'rb').read(),
            b'~BL\x00\x00\x00\x0812345678~EL\x00\x00\x00\x08')

    def test_contextmanager(self):
        fp = fileutil.LogFile('/test.log', 'w')
        with fp:
            fp.append(b'12345678', b'L')
        self.assertTrue(fp.closed)

    def test_read(self):
        with fileutil.LogFile('/test.log', 'w') as fp:
            fp.append(b'12345678', b'L')
            fp.append(b'abcd', b'D')
            fp.append(b'~~12~', b'B')

        with fileutil.LogFile('/test.log', 'r') as fp:
            self.assertEqual(
                [fp.read() for __type in range(3)],
                [(b'12345678', b'L'),
                 (b'abcd', b'D'),
                 (b'~~12~', b'B')])

            with self.assertRaises(EOFError):
                fp.read()

    def test_read_iterator(self):
        with fileutil.LogFile('/test.log', 'w') as fp:
            fp.append(b'12345678', b'L')
            fp.append(b'abcd', b'D')
            fp.append(b'~~12~', b'B')

        with fileutil.LogFile('/test.log', 'r') as fp:
            self.assertEqual(
                [(data, entry_type) for data, entry_type in fp],
                [(b'12345678', b'L'),
                 (b'abcd', b'D'),
                 (b'~~12~', b'B')])

    def test_read_truncated(self):
        with fileutil.LogFile('/test.log', 'w') as fp:
            fp.append(b'12345678', b'L')
        with self.fake_open('/test.log', 'rb') as fp:
            contents = fp.read()

        while len(contents) > 1:
            contents = contents[:-1]
            with self.fake_open('/test.log', 'wb') as fp:
                fp.write(contents)

            with fileutil.LogFile('/test.log', 'r') as fp:
                with self.assertRaises(fileutil.CorruptedFileError):
                    fp.read()

    def test_read_corrupted(self):
        with self.fake_open('/test.log', 'wb') as fp:
            fp.write(b'~BL\x00\x00\x00\x0812345678-EL\x00\x00\x00\x08')
            #                                     ^
        with fileutil.LogFile('/test.log', 'r') as fp:
            with self.assertRaises(fileutil.CorruptedFileError):
                fp.read()

        with self.fake_open('/test.log', 'wb') as fp:
            fp.write(b'~BL\x00\x00\x00\x0812345678~EE\x00\x00\x00\x08')
            #                                       ^
        with fileutil.LogFile('/test.log', 'r') as fp:
            with self.assertRaises(fileutil.CorruptedFileError):
                fp.read()

        with self.fake_open('/test.log', 'wb') as fp:
            fp.write(b'~BL\x00\x00\x00\x0812345678~EL\x00\x00\x00\x09')
            #                                                       ^
        with fileutil.LogFile('/test.log', 'r') as fp:
            with self.assertRaises(fileutil.CorruptedFileError):
                fp.read()


if __name__ == '__main__':
    unittest.main()
