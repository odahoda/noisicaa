#!/usr/bin/python3

import unittest
import textwrap

from . import fileutil

class FileTest(unittest.TestCase):
    def testWriteJson(self):
        fp = fileutil.File('/tmp/foo')
        fp.write_json(
            {'a': [0, 1, 2]},
            fileutil.FileInfo(filetype='test', version=1))

    def testRead(self):
        contents = textwrap.dedent("""\
            NOISICAA
            Version: 1
            File-Type: test
            Checksum: a6df13cacabe3782f0fb701806ead446; type="md5"
            Content-Type: application/json; charset="utf-8"
            Content-Length: 16

            {"a": [0, 1, 2]}""").encode('ascii')

        with open('/tmp/foo2', 'wb') as fp:
            fp.write(contents)

        fp = fileutil.File('/tmp/foo2')
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

        with open('/tmp/foo2', 'wb') as fp:
            fp.write(contents)

        fp = fileutil.File('/tmp/foo2')
        header, content = fp.read_json()
        self.assertEqual(header.version, 1)
        self.assertEqual(header.filetype, 'test')
        self.assertEqual(content, {'a': [0, 1, 2]})


if __name__ == '__main__':
    unittest.main()
