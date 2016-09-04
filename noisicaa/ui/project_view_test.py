#!/usr/bin/python3

import unittest

from . import uitest_utils
from . import sheet_view
from . import project_view
from . import model
from . import sheet_property_track_item

class SheetPropertyMeasureItem(
        uitest_utils.TestMixin,
        sheet_property_track_item.SheetPropertyMeasureItemImpl):
    pass

class SheetPropertyTrackItem(
        uitest_utils.TestMixin,
        sheet_property_track_item.SheetPropertyTrackItemImpl):
    measure_item_cls = SheetPropertyMeasureItem

class SheetView(uitest_utils.TestMixin, sheet_view.SheetViewImpl):
    track_cls_map = {
        'SheetPropertyTrack': SheetPropertyTrackItem,
    }

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class ProjectView(uitest_utils.TestMixin, project_view.ProjectViewImpl):
    def createSheetView(self, **kwargs):
        return SheetView(**kwargs)


class InitTest(uitest_utils.UITest):
    async def test_init_with_no_sheets(self):
        view = ProjectView(**self.context)
        await view.setup()
        self.assertIsNone(view.currentSheetView())

    async def test_init_with_sheets(self):
        self.project.sheets.append(model.Sheet('sheet1'))
        self.project.sheets[0].property_track = model.SheetPropertyTrack('prop1')
        self.project.sheets[0].master_group = model.TrackGroup('master')
        self.project.sheets.append(model.Sheet('sheet2'))
        self.project.sheets[1].property_track = model.SheetPropertyTrack('prop2')
        self.project.sheets[1].master_group = model.TrackGroup('master')
        view = ProjectView(**self.context)
        await view.setup()
        self.assertIsInstance(view.currentSheetView(), SheetView)
        self.assertEqual(view.currentSheetView().sheet.id, 'sheet1')
        for sheet_view in view.sheetViews:
            self.assertIsInstance(view.currentSheetView(), SheetView)
        self.assertEqual(len(list(view.sheetViews)), 2)


class ModelChangesTest(uitest_utils.UITest):
    # TODO: the change handler is async, need to wait until it was run
    #   before checking that state of the sheetViews list.
    pass

    # async def test_add_sheet(self):
    #     view = ProjectView(**self.context)
    #     await view.setup()
    #     self.assertEqual(len(list(view.sheetViews)), 0)

    #     sheet = model.Sheet('sheet1')
    #     sheet.property_track = model.SheetPropertyTrack('prop1')
    #     self.project.sheets.append(sheet)
    #     self.assertEqual(len(list(view.sheetViews)), 1)

    # async def test_remove_sheet(self):
    #     sheet = model.Sheet('sheet1')
    #     sheet.property_track = model.SheetPropertyTrack('prop1')
    #     self.project.sheets.append(sheet)

    #     view = ProjectView(**self.context)
    #     await view.setup()
    #     self.assertEqual(len(list(view.sheetViews)), 1)

    #     del self.project.sheets[0]
    #     self.assertEqual(len(list(view.sheetViews)), 0)

    # async def test_clear_sheets(self):
    #     sheet = model.Sheet('sheet1')
    #     sheet.property_track = model.SheetPropertyTrack('prop1')
    #     self.project.sheets.append(sheet)

    #     view = ProjectView(**self.context)
    #     await view.setup()
    #     self.assertEqual(len(list(view.sheetViews)), 1)

    #     self.project.sheets.clear()
    #     self.assertEqual(len(list(view.sheetViews)), 0)


class CommandsTest(uitest_utils.UITest):
    async def test_onAddSheet(self):
        sheet = model.Sheet('sheet1')
        sheet.name = 'Sheet 1'
        sheet.property_track = model.SheetPropertyTrack('prop1')
        sheet.master_group = model.TrackGroup('master')
        self.project.sheets.append(sheet)

        view = ProjectView(**self.context)
        await view.setup()
        view.onAddSheet()
        self.assertEqual(
            self.commands,
            [('project', 'AddSheet', {})])

    async def test_onDeleteSheet(self):
        sheet = model.Sheet('sheet1')
        sheet.name = 'Sheet 1'
        sheet.property_track = model.SheetPropertyTrack('prop1')
        sheet.master_group = model.TrackGroup('master')
        self.project.sheets.append(sheet)
        sheet = model.Sheet('sheet2')
        sheet.name = 'Sheet 2'
        sheet.property_track = model.SheetPropertyTrack('prop2')
        sheet.master_group = model.TrackGroup('master')
        self.project.sheets.append(sheet)

        view = ProjectView(**self.context)
        await view.setup()
        view.onDeleteSheet()
        self.assertEqual(
            self.commands,
            [('project', 'DeleteSheet', {'name': 'Sheet 1'})])

    # def test_onAddTrack(self):
    #     self.project.sheets.append(music.Sheet(name="test1"))
    #     view = project_view.ProjectView(self.app, self.window, self.project)

    #     self.project.dispatch_command.side_effect = None
    #     view.onAddTrack('score')
    #     self.assertEqual(self.project.dispatch_command.call_count, 1)
    #     (target, cmd), _ = self.project.dispatch_command.call_args
    #     #self.assertEqual(target, '/sheet:test1')
    #     self.assertEqual(cmd, music.AddTrack(track_type='score'))

    # def test_onPlayerCommands(self):
    #     self.project.sheets.append(music.Sheet(name="test1"))
    #     view = project_view.ProjectView(self.app, self.window, self.project)
    #     view.onPlayerStart()
    #     view.onPlayerPause()
    #     view.onPlayerStart()
    #     view.onPlayerStop()

    # def test_currentTool(self):
    #     view = project_view.ProjectView(self.app, self.window, self.project)
    #     self.assertIsNone(view.currentTool())
    #     view.setCurrentTool(Tool.NOTE_HALF)
    #     self.assertIsNone(view.currentTool())

    #     self.project.sheets.append(music.Sheet(name="test1"))
    #     view.setCurrentTool(Tool.NOTE_HALF)
    #     self.assertEqual(view.currentTool(), Tool.NOTE_HALF)


if __name__ == '__main__':
    unittest.main()
