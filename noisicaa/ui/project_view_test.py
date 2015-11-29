#/usr/bin/python3

import unittest
from unittest import mock

from PyQt5.QtGui import QCloseEvent

from noisicaa import music
from . import uitest_utils
from .editor_project import EditorProject
from .tool_dock import Tool
from .sheet_view import SheetView
from . import project_view


class ProjectViewTest(uitest_utils.UITest):
    def setUp(self):
        super().setUp()
        self.window = None
        self.project = EditorProject(self.app)
        self.project.sheets.clear()
        self.project.dispatch_command = mock.MagicMock()
        self.project.dispatch_command.side_effect = AssertionError(
            "Unexpected command")

    def test_initWithNoSheets(self):
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertIsNone(view.currentSheetView())

    def test_initWithSheets(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        self.project.sheets.append(music.Sheet(name="test2"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertIsInstance(view.currentSheetView(), SheetView)

    def test_properties(self):
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertIs(view.project, self.project)

    def test_addSheet(self):
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertEqual(len(list(view.sheetViews)), 0)
        self.project.sheets.append(music.Sheet(name="test"))
        self.assertEqual(len(list(view.sheetViews)), 1)

    def test_removeSheet(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        self.project.sheets.append(music.Sheet(name="test2"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertEqual(len(list(view.sheetViews)), 2)
        del self.project.sheets[1]
        self.assertEqual(len(list(view.sheetViews)), 1)

    def test_clearSheets(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        self.project.sheets.append(music.Sheet(name="test2"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertEqual(len(list(view.sheetViews)), 2)
        self.project.sheets.clear()
        self.assertEqual(len(list(view.sheetViews)), 0)

    def test_closeEvent(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        event = QCloseEvent()
        view.closeEvent(event)
        self.assertEqual(len(list(view.sheetViews)), 0)

    def test_closeEventWithChanges(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.project.changed_since_last_checkpoint = True
        self.project.write_checkpoint = mock.MagicMock()
        event = QCloseEvent()
        view.closeEvent(event)
        self.assertEqual(len(list(view.sheetViews)), 0)
        self.assertEqual(self.project.write_checkpoint.call_count, 1)

    def test_onAddSheet(self):
        view = project_view.ProjectView(self.app, self.window, self.project)

        self.project.dispatch_command.side_effect = None
        view.onAddSheet()
        self.assertEqual(self.project.dispatch_command.call_count, 1)
        (target, cmd), _ = self.project.dispatch_command.call_args
        self.assertEqual(target, '/')
        self.assertIsInstance(cmd, music.AddSheet)

    def test_onDeleteSheet(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        self.project.sheets.append(music.Sheet(name="test2"))
        view = project_view.ProjectView(self.app, self.window, self.project)

        self.project.dispatch_command.side_effect = None
        view.onDeleteSheet()
        self.assertEqual(self.project.dispatch_command.call_count, 1)
        (target, cmd), _ = self.project.dispatch_command.call_args
        self.assertEqual(target, '/')
        self.assertIsInstance(cmd, music.DeleteSheet)
        self.assertEqual(cmd.name, 'test1')

    def test_onAddTrack(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        view = project_view.ProjectView(self.app, self.window, self.project)

        self.project.dispatch_command.side_effect = None
        view.onAddTrack('score')
        self.assertEqual(self.project.dispatch_command.call_count, 1)
        (target, cmd), _ = self.project.dispatch_command.call_args
        self.assertEqual(target, '/sheet:test1')
        self.assertIsInstance(cmd, music.AddTrack)

    def test_onPlayerCommands(self):
        self.project.sheets.append(music.Sheet(name="test1"))
        view = project_view.ProjectView(self.app, self.window, self.project)
        view.onPlayerStart()
        view.onPlayerPause()
        view.onPlayerStart()
        view.onPlayerStop()

    def test_currentTool(self):
        view = project_view.ProjectView(self.app, self.window, self.project)
        self.assertIsNone(view.currentTool())
        view.setCurrentTool(Tool.NOTE_HALF)
        self.assertIsNone(view.currentTool())

        self.project.sheets.append(music.Sheet(name="test1"))
        view.setCurrentTool(Tool.NOTE_HALF)
        self.assertEqual(view.currentTool(), Tool.NOTE_HALF)

if __name__ == '__main__':
    unittest.main()
