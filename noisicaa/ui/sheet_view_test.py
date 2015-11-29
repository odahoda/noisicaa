#/usr/bin/python3

import unittest
from unittest import mock

from PyQt5.QtGui import QCloseEvent

from noisicaa import music
from . import uitest_utils
from .editor_project import EditorProject
from .tool_dock import Tool
from .sheet_view import SheetView
from . import sheet_view


class SheetViewTest(uitest_utils.UITest):
    def setUp(self):
        super().setUp()
        self.window = None
        self.project = EditorProject(self.app)
        self.project.sheets.clear()
        self.project.dispatch_command = mock.MagicMock()
        self.project.dispatch_command.side_effect = AssertionError(
            "Unexpected command")
        self.sheet = music.Sheet(name='test')
        self.project.sheets.append(self.sheet)

    def test_init(self):
        view = sheet_view.SheetView(None, self.app, self.window, self.sheet)
        #self.assertIsNone(view.currentSheetView())

    def test_insert_measure(self):
        view = sheet_view.SheetView(None, self.app, self.window, self.sheet)

        cmd = music.InsertMeasure(tracks=[], pos=0)
        with view.inhibitUpdates():
            cmd.run(self.sheet)


if __name__ == '__main__':
    unittest.main()
