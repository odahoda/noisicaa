#/usr/bin/python3

import unittest
from unittest import mock

from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QMenu

from noisicaa import music
from . import uitest_utils
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
        self.project.dispatch_command.side_effect = self.failureException(
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


class MeasureItemTest(uitest_utils.UITest):
    def setUp(self):
        super().setUp()
        self.window = None
        self.project = EditorProject(self.app)
        self.project.sheets.clear()
        self.project.dispatch_command = mock.MagicMock()
        self.project.dispatch_command.side_effect = self.failureException(
            "Unexpected command")
        self.sheet = music.Sheet(name='test')
        self.project.sheets.append(self.sheet)

    def test_menu_insert_measure(self):
        self.project.dispatch_command.side_effect = None

        view = sheet_view.SheetView(None, self.app, self.window, self.sheet)
        track = view._tracks[0]
        measure = track.measures[0]

        # Not the best way to find and trigger a context menu action...
        menu = QMenu()
        measure.buildContextMenu(menu)
        for action in menu.actions():
            if action.text() == "Insert measure":
                action.trigger()
                break
        else:
            self.fail("No 'Insert measure' menu item found.")

        self.assertEqual(self.project.dispatch_command.call_count, 1)
        (target, cmd), _ = self.project.dispatch_command.call_args
        self.assertEqual(target, '/sheet:test')
        self.assertEqual(cmd, music.InsertMeasure(tracks=[0], pos=0))

    def test_menu_remove_measure(self):
        self.project.dispatch_command.side_effect = None

        view = sheet_view.SheetView(None, self.app, self.window, self.sheet)
        track = view._tracks[0]
        measure = track.measures[0]

        # Not the best way to find and trigger a context menu action...
        menu = QMenu()
        measure.buildContextMenu(menu)
        for action in menu.actions():
            if action.text() == "Remove measure":
                action.trigger()
                break
        else:
            self.fail("No 'Remove measure' menu item found.")

        self.assertEqual(self.project.dispatch_command.call_count, 1)
        (target, cmd), _ = self.project.dispatch_command.call_args
        self.assertEqual(target, '/sheet:test')
        self.assertEqual(cmd, music.RemoveMeasure(tracks=[0], pos=0))


if __name__ == '__main__':
    unittest.main()
