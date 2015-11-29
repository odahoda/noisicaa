#!/usr/bin/python3

import unittest

from . import editor_project
from ..audioproc.pipeline import Pipeline

class FakeApp(object):
    def __init__(self):
        self.pipeline = Pipeline()

class EditorProjectTest(unittest.TestCase):
    def testCreate(self):
        p = editor_project.EditorProject(FakeApp())
        p.close()


if __name__ == '__main__':
    unittest.main()
