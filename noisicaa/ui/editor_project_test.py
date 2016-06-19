#!/usr/bin/python3

import unittest

from . import editor_project

class FakeApp(object):
    pass


class EditorProjectTest(unittest.TestCase):
    def testCreate(self):
        p = editor_project.EditorProject(FakeApp())
        p.close()


if __name__ == '__main__':
    unittest.main()
