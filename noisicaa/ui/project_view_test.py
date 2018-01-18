#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

# from unittest import mock

# from PyQt5.QtCore import Qt
# from PyQt5 import QtCore
# from PyQt5 import QtGui

# from noisidev import unittest
# from . import uitest_utils
# from . import project_view
# from . import model
# from . import tool_dock
# from . import track_items


# class InitTest(uitest_utils.UITest):
#     async def test_init(self):
#         view = ProjectView(**self.context_args)
#         await view.setup()
#         self.assertIsNone(view.currentSheetView())
#
#     async def test_init_with_sheets(self):
#         self.project.sheets.append(model.Sheet('sheet1'))
#         self.project.sheets[0].property_track = model.SheetPropertyTrack('prop1')
#         self.project.sheets[0].master_group = model.TrackGroup('master')
#         self.project.sheets.append(model.Sheet('sheet2'))
#         self.project.sheets[1].property_track = model.SheetPropertyTrack('prop2')
#         self.project.sheets[1].master_group = model.TrackGroup('master')
#         view = ProjectView(**self.context_args)
#         await view.setup()
#         self.assertIsInstance(view.currentSheetView(), SheetView)
#         self.assertEqual(view.currentSheetView().sheet.id, 'sheet1')
#         for sheet_view in view.sheetViews:
#             self.assertIsInstance(view.currentSheetView(), SheetView)
#         self.assertEqual(len(list(view.sheetViews)), 2)


# class ModelChangesTest(uitest_utils.UITest):
#     # TODO: the change handler is async, need to wait until it was run
#     #   before checking that state of the sheetViews list.
#     pass

#     # async def test_add_sheet(self):
#     #     view = ProjectView(**self.context_args)
#     #     await view.setup()
#     #     self.assertEqual(len(list(view.sheetViews)), 0)

#     #     sheet = model.Sheet('sheet1')
#     #     sheet.property_track = model.SheetPropertyTrack('prop1')
#     #     self.project.sheets.append(sheet)
#     #     self.assertEqual(len(list(view.sheetViews)), 1)

#     # async def test_remove_sheet(self):
#     #     sheet = model.Sheet('sheet1')
#     #     sheet.property_track = model.SheetPropertyTrack('prop1')
#     #     self.project.sheets.append(sheet)

#     #     view = ProjectView(**self.context_args)
#     #     await view.setup()
#     #     self.assertEqual(len(list(view.sheetViews)), 1)

#     #     del self.project.sheets[0]
#     #     self.assertEqual(len(list(view.sheetViews)), 0)

#     # async def test_clear_sheets(self):
#     #     sheet = model.Sheet('sheet1')
#     #     sheet.property_track = model.SheetPropertyTrack('prop1')
#     #     self.project.sheets.append(sheet)

#     #     view = ProjectView(**self.context_args)
#     #     await view.setup()
#     #     self.assertEqual(len(list(view.sheetViews)), 1)

#     #     self.project.sheets.clear()
#     #     self.assertEqual(len(list(view.sheetViews)), 0)


# class CommandsTest(uitest_utils.UITest):
#     async def test_onAddSheet(self):
#         sheet = model.Sheet('sheet1')
#         sheet.name = 'Sheet 1'
#         sheet.property_track = model.SheetPropertyTrack('prop1')
#         sheet.master_group = model.TrackGroup('master')
#         self.project.sheets.append(sheet)

#         view = ProjectView(**self.context_args)
#         await view.setup()
#         view.onAddSheet()
#         self.assertEqual(
#             self.commands,
#             [('project', 'AddSheet', {})])

#     async def test_onDeleteSheet(self):
#         sheet = model.Sheet('sheet1')
#         sheet.name = 'Sheet 1'
#         sheet.property_track = model.SheetPropertyTrack('prop1')
#         sheet.master_group = model.TrackGroup('master')
#         self.project.sheets.append(sheet)
#         sheet = model.Sheet('sheet2')
#         sheet.name = 'Sheet 2'
#         sheet.property_track = model.SheetPropertyTrack('prop2')
#         sheet.master_group = model.TrackGroup('master')
#         self.project.sheets.append(sheet)

#         view = ProjectView(**self.context_args)
#         await view.setup()
#         view.onDeleteSheet()
#         self.assertEqual(
#             self.commands,
#             [('project', 'DeleteSheet', {'name': 'Sheet 1'})])

#     # def test_onAddTrack(self):
#     #     self.project.sheets.append(music.Sheet(name="test1"))
#     #     view = project_view.ProjectView(self.app, self.window, self.project)

#     #     self.project.dispatch_command.side_effect = None
#     #     view.onAddTrack('score')
#     #     self.assertEqual(self.project.dispatch_command.call_count, 1)
#     #     (target, cmd), _ = self.project.dispatch_command.call_args
#     #     #self.assertEqual(target, '/sheet:test1')
#     #     self.assertEqual(cmd, music.AddTrack(track_type='score'))

#     # def test_onPlayerCommands(self):
#     #     self.project.sheets.append(music.Sheet(name="test1"))
#     #     view = project_view.ProjectView(self.app, self.window, self.project)
#     #     view.onPlayerStart()
#     #     view.onPlayerPause()
#     #     view.onPlayerStart()
#     #     view.onPlayerStop()

#     # def test_currentTool(self):
#     #     view = project_view.ProjectView(self.app, self.window, self.project)
#     #     self.assertIsNone(view.currentTool())
#     #     view.setCurrentTool(Tool.NOTE_HALF)
#     #     self.assertIsNone(view.currentTool())

#     #     self.project.sheets.append(music.Sheet(name="test1"))
#     #     view.setCurrentTool(Tool.NOTE_HALF)
#     #     self.assertEqual(view.currentTool(), Tool.NOTE_HALF)



# class SheetViewTest(uitest_utils.UITest):
#     async def setup_testcase(self):
#         await super().setup_testcase()

#         self.sheet = model.Sheet('sheet1')
#         self.sheet.name = 'Sheet 1'
#         self.sheet.property_track = model.SheetPropertyTrack('prop1')
#         self.sheet.master_group = model.TrackGroup('master')
#         self.project.sheets.append(self.sheet)


# class SheetViewInitTest(SheetViewTest):
#     async def test_init(self):
#         track = model.ScoreTrack('track1')
#         self.sheet.master_group.tracks.append(track)
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()
#         self.assertEqual(
#             [ti.track.id for ti in view.trackItems],
#             ['track1'])


# class SheetViewModelChangesTest(SheetViewTest):
#     async def test_tracks(self):
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()

#         track = model.ScoreTrack('track1')
#         self.sheet.master_group.tracks.append(track)
#         track = model.ScoreTrack('track2')
#         self.sheet.master_group.tracks.append(track)
#         self.assertEqual(
#             [ti.track.id for ti in view.trackItems],
#             ['track1', 'track2'])

#         del self.sheet.master_group.tracks[0]
#         self.assertEqual(
#             [ti.track.id for ti in view.trackItems],
#             ['track2'])
#         self.assertEqual(len(view.trackItems), 1)

#         self.sheet.master_group.tracks.clear()
#         self.assertEqual(
#             [ti.track.id for ti in view.trackItems],
#             [])

#     async def test_track_visibility(self):
#         track = model.ScoreTrack('track1')
#         self.sheet.master_group.tracks.append(track)
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()
#         view.updateSheet = mock.MagicMock()
#         self.assertEqual(view.updateSheet.call_count, 0)
#         track.visible = False
#         self.assertEqual(view.updateSheet.call_count, 1)


# class SheetViewCommandsTest(SheetViewTest):
#     async def test_onAddTrack(self):
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()
#         view.onAddTrack('score')
#         self.assertEqual(
#             self.commands,
#             [('sheet1', 'AddTrack', {'track_type': 'score'})])


# class SheetViewEventsTest(SheetViewTest):
#     async def test_keyEvent(self):
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()

#         # Number keys select notes, if the current tool is a note.
#         view.setCurrentTool(tool_dock.Tool.NOTE_QUARTER)
#         for key, mod, tool in [
#                 (Qt.Key_1, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_WHOLE),
#                 (Qt.Key_2, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_HALF),
#                 (Qt.Key_3, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_QUARTER),
#                 (Qt.Key_4, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_8TH),
#                 (Qt.Key_5, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_16TH),
#                 (Qt.Key_6, Qt.NoModifier,
#                  tool_dock.Tool.NOTE_32TH),
#         ]:
#             view.event(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, mod))
#             self.assertEqual(view.currentTool(), tool)

#         # If the current tool is a rest, then numbers select rests.
#         view.setCurrentTool(tool_dock.Tool.REST_QUARTER)
#         for key, mod, tool in [
#                 (Qt.Key_1, Qt.NoModifier,
#                  tool_dock.Tool.REST_WHOLE),
#                 (Qt.Key_2, Qt.NoModifier,
#                  tool_dock.Tool.REST_HALF),
#                 (Qt.Key_3, Qt.NoModifier,
#                  tool_dock.Tool.REST_QUARTER),
#                 (Qt.Key_4, Qt.NoModifier,
#                  tool_dock.Tool.REST_8TH),
#                 (Qt.Key_5, Qt.NoModifier,
#                  tool_dock.Tool.REST_16TH),
#                 (Qt.Key_6, Qt.NoModifier,
#                  tool_dock.Tool.REST_32TH),
#         ]:
#             view.event(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, mod))
#             self.assertEqual(view.currentTool(), tool)

#         # 'r' switches between notes and rests of the same duration.
#         view.setCurrentTool(tool_dock.Tool.NOTE_8TH)
#         view.event(QtGui.QKeyEvent(
#             QtCore.QEvent.KeyPress, Qt.Key_R, Qt.NoModifier))
#         self.assertEqual(view.currentTool(), tool_dock.Tool.REST_8TH)
#         view.event(QtGui.QKeyEvent(
#             QtCore.QEvent.KeyPress, Qt.Key_R, Qt.NoModifier))
#         self.assertEqual(view.currentTool(), tool_dock.Tool.NOTE_8TH)

#         # "modifier" tools return back to previous tool, when key is
#         # released.
#         view.setCurrentTool(tool_dock.Tool.NOTE_QUARTER)
#         for key, mod, tool in [
#                 (Qt.Key_N, Qt.NoModifier,
#                  tool_dock.Tool.ACCIDENTAL_NATURAL),
#                 (Qt.Key_F, Qt.NoModifier,
#                  tool_dock.Tool.ACCIDENTAL_FLAT),
#                 (Qt.Key_S, Qt.NoModifier,
#                  tool_dock.Tool.ACCIDENTAL_SHARP),
#                 (Qt.Key_Period, Qt.NoModifier,
#                  tool_dock.Tool.DURATION_DOT),
#         ]:
#             view.event(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, mod))
#             self.assertEqual(view.currentTool(), tool)
#             view.event(QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, key, mod))
#             self.assertEqual(
#                 view.currentTool(), tool_dock.Tool.NOTE_QUARTER)

#         # A key press that has no function.
#         view.event(QtGui.QKeyEvent(
#             QtCore.QEvent.KeyPress, Qt.Key_SysReq, Qt.NoModifier))
#         view.event(QtGui.QKeyEvent(
#             QtCore.QEvent.KeyRelease, Qt.Key_SysReq, Qt.NoModifier))


# class SheetViewToolTest(SheetViewTest):
#     # This one just aims for coverage. TODO: also verify effects.
#     async def test_setCurrentTool(self):
#         view = SheetView(**self.context_args, sheet=self.sheet)
#         await view.setup()

#         for tool in tool_dock.Tool:
#             with self.subTest(tool=tool):
#                 view.setCurrentTool(tool)
#                 self.assertEqual(view.currentTool(), tool)

#         with self.assertRaises(ValueError):
#             view.setCurrentTool(-1)

#         view.setCurrentTool(view.currentTool())

# class MeasureItemTest(uitest_utils.UITest):
#     def setup_testcase(self):
#         super().setup_testcase()
#         self.window = None
#         self.project = EditorProject(self.app)
#         self.project.sheets.clear()
#         self.project.dispatch_command = mock.MagicMock()
#         self.project.dispatch_command.side_effect = self.failureException(
#             "Unexpected command")
#         self.sheet = music.Sheet(name='test')
#         self.project.sheets.append(self.sheet)

#     def test_menu_insert_measure(self):
#         self.project.dispatch_command.side_effect = None

#         view = sheet_view.SheetView(None, self.app, self.window, self.sheet)
#         track = view._tracks[0]
#         measure = track.measure_list[0].measure

#         # Not the best way to find and trigger a context menu action...
#         menu = QMenu()
#         measure.buildContextMenu(menu)
#         for action in menu.actions():
#             if action.text() == "Insert measure":
#                 action.trigger()
#                 break
#         else:
#             self.fail("No 'Insert measure' menu item found.")

#         self.assertEqual(self.project.dispatch_command.call_count, 1)
#         (target, cmd), _ = self.project.dispatch_command.call_args
#         self.assertEqual(target, '/sheet:test')
#         self.assertEqual(cmd, music.InsertMeasure(tracks=[0], pos=0))

#     def test_menu_remove_measure(self):
#         self.project.dispatch_command.side_effect = None

#         view = sheet_view.SheetView(None, self.app, self.window, self.sheet)
#         track = view._tracks[0]
#         measure = track.measure_list[0].measure

#         # Not the best way to find and trigger a context menu action...
#         menu = QMenu()
#         measure.buildContextMenu(menu)
#         for action in menu.actions():
#             if action.text() == "Remove measure":
#                 action.trigger()
#                 break
#         else:
#             self.fail("No 'Remove measure' menu item found.")

#         self.assertEqual(self.project.dispatch_command.call_count, 1)
#         (target, cmd), _ = self.project.dispatch_command.call_args
#         self.assertEqual(target, '/sheet:test')
#         self.assertEqual(cmd, music.RemoveMeasure(tracks=[0], pos=0))
