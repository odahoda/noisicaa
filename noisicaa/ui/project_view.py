#!/usr/bin/python3

import logging

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from . import sheet_view
from . import tool_dock
from . import ui_base

logger = logging.getLogger(__name__)


class ProjectViewImpl(QtWidgets.QWidget):
    currentToolChanged = QtCore.pyqtSignal(tool_dock.Tool)
    currentSheetChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._sheets_widget = QtWidgets.QStackedWidget(self)
        self._sheets_widget.currentChanged.connect(
            self.onCurrentSheetChanged)

        self._current_sheet_view = None

        self.sheet_menu = QtWidgets.QMenu()
        self.updateSheetMenu()

        # Sheet selection should better be in a dock...
        sheet_menu_button = QtWidgets.QToolButton(self)
        sheet_menu_button.setIcon(QtGui.QIcon.fromTheme('start-here'))
        sheet_menu_button.setMenu(self.sheet_menu)
        sheet_menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        player_status = QtWidgets.QWidget(self)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(sheet_menu_button)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(player_status)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._sheets_widget)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

        self._sheet_listener = self.project.listeners.add(
            'sheets',
            lambda *args, **kwargs: self.call_async(
                self.onSheetsChanged(*args, **kwargs)))

    async def setup(self):
        for sheet in self.project.sheets:
            view = self.createSheetView(
                **self.context, sheet=sheet, parent=self)
            await view.setup()
            self._sheets_widget.addWidget(view)

        # TODO: Persist what was the current sheet.
        if self._sheets_widget.count() > 0:
            self.setCurrentSheetView(self._sheets_widget.widget(0))

    async def cleanup(self):
        while self._sheets_widget.count() > 0:
            sheet_view = self._sheets_widget.widget(0)
            self._sheets_widget.removeWidget(sheet_view)
            await sheet_view.cleanup()

    @property
    def sheetViews(self):
        for idx in range(self._sheets_widget.count()):
            yield self._sheets_widget.widget(idx)

    def currentTool(self):
        if self.currentSheetView() is not None:
            return self.currentSheetView().currentTool()
        return None

    def setCurrentTool(self, tool):
        if self.currentSheetView() is not None:
            self.currentSheetView().setCurrentTool(tool)

    def currentSheetView(self):
        return self._sheets_widget.currentWidget()

    def setCurrentSheetView(self, sheet_view):
        if sheet_view == self._current_sheet_view:
            return

        if self._current_sheet_view is not None:
            self._current_sheet_view.currentToolChanged.disconnect(
                self.currentToolChanged)

        if sheet_view is not None:
            sheet_view.currentToolChanged.connect(
                self.currentToolChanged)

        self._current_sheet_view = sheet_view

        if sheet_view is not None:
            self.currentSheetChanged.emit(sheet_view.sheet)
        else:
            self.currentSheetChanged.emit(None)

    def updateView(self):
        for sheet_view in self.sheetViews:
            sheet_view.updateView()

    async def onSheetsChanged(self, action, *args):
        if action == 'insert':
            idx, sheet = args
            view = self.createSheetView(
                **self.context, sheet=sheet, parent=self)
            await view.setup()
            self._sheets_widget.insertWidget(idx, view)
            self.updateSheetMenu()

        elif action == 'delete':
            idx, = args
            view = self._sheets_widget.widget(idx)
            self._sheets_widget.removeWidget(view)
            await view.cleanup()
            self.updateSheetMenu()

        else:  # pragma: no cover
            raise AssertionError("Unknown action %r" % action)

    def updateSheetMenu(self):
        self.sheet_menu.clear()

        action = self.sheet_menu.addAction(
            QtGui.QIcon.fromTheme('document-new'), "Add Sheet")
        action.triggered.connect(self.onAddSheet)

        action = self.sheet_menu.addAction(
            QtGui.QIcon.fromTheme('edit-delete'), "Delete Sheet")
        action.setEnabled(len(self.project.sheets) > 1)
        action.triggered.connect(self.onDeleteSheet)

        self.sheet_menu.addSeparator()
        for idx, sheet in enumerate(self.project.sheets): # pylint: disable=unused-variable
            action = self.sheet_menu.addAction(
                QtGui.QIcon.fromTheme('audio-x-generic'), sheet.name)
            action.triggered.connect(
                lambda _, idx=idx: self._sheets_widget.setCurrentIndex(idx))

    def onCurrentSheetChanged(self, idx):
        if idx >= 0:
            sheet_view = self._sheets_widget.widget(idx)
        else:
            sheet_view = None
        self.setCurrentSheetView(sheet_view)

    def onAddSheet(self):
        self.send_command_async(self.project.id, 'AddSheet')

    def onDeleteSheet(self):
        assert len(self.project.sheets) > 1
        self.send_command_async(
            self.project.id, 'DeleteSheet',
            name=self.currentSheetView().sheet.name)

    def onPlayerStart(self):
        view = self.currentSheetView()
        view.onPlayerStart()

    def onPlayerPause(self):
        view = self.currentSheetView()
        view.onPlayerPause()

    def onPlayerStop(self):
        view = self.currentSheetView()
        view.onPlayerStop()

    def onAddTrack(self, track_type):
        view = self.currentSheetView()
        view.onAddTrack(track_type)

    def onRender(self):
        view = self.currentSheetView()
        view.onRender()


class ProjectView(ui_base.ProjectMixin, ProjectViewImpl):
    def createSheetView(self, **kwargs):  # pragma: no cover
        return sheet_view.SheetView(**kwargs)
