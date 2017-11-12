#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import functools
import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import tool_dock
from . import sheet_properties_dock
from . import tracks_dock
from . import track_properties_dock
from . import pipeline_graph_view
from . import sheet_view
from . import tool_dock
from . import ui_base
from . import tools

logger = logging.getLogger(__name__)


class ProjectViewImpl(QtWidgets.QMainWindow):
    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    playbackStateChanged = QtCore.pyqtSignal(str)
    playbackLoopChanged = QtCore.pyqtSignal(bool)
    currentSheetChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs):
        super().__init__(parent=None, flags=Qt.Widget, **kwargs)

        sheet_tab = QtWidgets.QWidget()

        self._sheets_widget = QtWidgets.QStackedWidget(sheet_tab)
        self._sheets_widget.currentChanged.connect(
            self.onCurrentSheetChanged)

        self._current_sheet_view = None

        self.sheet_menu = QtWidgets.QMenu()
        self.updateSheetMenu()

        # Sheet selection should better be in a dock...
        sheet_menu_button = QtWidgets.QToolButton(sheet_tab)
        sheet_menu_button.setIcon(QtGui.QIcon.fromTheme('start-here'))
        sheet_menu_button.setMenu(self.sheet_menu)
        sheet_menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(sheet_menu_button)
        bottom_layout.addStretch(1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(self._sheets_widget)
        layout.addLayout(bottom_layout)
        sheet_tab.setLayout(layout)

        mixer_tab = QtWidgets.QWidget()

        graph_tab = pipeline_graph_view.PipelineGraphView(**self.context)

        project_tab = QtWidgets.QTabWidget(self)
        project_tab.setTabPosition(QtWidgets.QTabWidget.West)
        project_tab.setDocumentMode(True)
        project_tab.addTab(sheet_tab, "Sheet")
        project_tab.addTab(mixer_tab, "Mixer")
        project_tab.setTabEnabled(1, False)
        project_tab.addTab(graph_tab, "Graph")
        project_tab.setCurrentIndex(self.get_session_value(
            'project_view/current_tab_index', 0))
        project_tab.currentChanged.connect(functools.partial(
            self.set_session_value, 'project_view/current_tab_index'))
        self.setCentralWidget(project_tab)

        self._docks = []

        self._tools_dock = tool_dock.ToolsDockWidget(parent=self, **self.context)
        self._docks.append(self._tools_dock)
        self.currentToolBoxChanged.connect(self._tools_dock.setCurrentToolBox)

        self._sheet_properties_dock = sheet_properties_dock.SheetPropertiesDockWidget(
            parent=self, **self.context)
        self._docks.append(self._sheet_properties_dock)
        self.currentSheetChanged.connect(self._sheet_properties_dock.setSheet)

        self._tracks_dock = tracks_dock.TracksDockWidget(parent=self, **self.context)
        self._docks.append(self._tracks_dock)
        self.currentSheetChanged.connect(self._tracks_dock.setCurrentSheet)

        self._track_properties_dock = track_properties_dock.TrackPropertiesDockWidget(parent=self, **self.context)
        self._docks.append(self._track_properties_dock)
        self._tracks_dock.currentTrackChanged.connect(self._track_properties_dock.setTrack)

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

    def playbackState(self):
        if self._current_sheet_view is not None:
            return self._current_sheet_view.playbackState()
        return 'stopped'

    def playbackLoop(self):
        if self._current_sheet_view is not None:
            return self._current_sheet_view.playbackLoop()
        return False

    def currentSheetView(self):
        return self._sheets_widget.currentWidget()

    def setCurrentSheetView(self, sheet_view):
        if sheet_view == self._current_sheet_view:
            return

        if self._current_sheet_view is not None:
            self._current_sheet_view.currentToolBoxChanged.disconnect(
                self.currentToolBoxChanged)
            self._current_sheet_view.playbackStateChanged.disconnect(
                self.playbackStateChanged)
            self._current_sheet_view.playbackLoopChanged.disconnect(
                self.playbackLoopChanged)

        if sheet_view is not None:
            sheet_view.currentToolBoxChanged.connect(self.currentToolBoxChanged)
            self.currentToolBoxChanged.emit(sheet_view.currentToolBox())

            sheet_view.playbackStateChanged.connect(
                self.playbackStateChanged)
            self.playbackStateChanged.emit(sheet_view.playbackState())

            sheet_view.playbackLoopChanged.connect(
                self.playbackLoopChanged)
            self.playbackLoopChanged.emit(sheet_view.playbackLoop())

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
            idx, sheet = args
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

    def onPlayerMoveTo(self, where):
        view = self.currentSheetView()
        view.onPlayerMoveTo(where)

    def onPlayerToggle(self):
        view = self.currentSheetView()
        view.onPlayerToggle()

    def onPlayerLoop(self, loop):
        view = self.currentSheetView()
        view.onPlayerLoop(loop)

    def onRender(self):
        view = self.currentSheetView()
        view.onRender()

    def onClearSelection(self):
        view = self.currentSheetView()
        view.onClearSelection()

    def onCopy(self):
        if self.selection_set.empty():
            return

        self.call_async(self.onCopyAsync())

    async def onCopyAsync(self):
        data = []
        for item in sorted(self.selection_set, key=lambda item: item.measure_reference.index):
            data.append(await item.getCopy())

        self.app.setClipboardContent(
            {'type': 'measures', 'data': data})

    def onPaste(self, *, mode):
        view = self.currentSheetView()
        view.onPaste(mode=mode)


class ProjectView(ui_base.ProjectMixin, ProjectViewImpl):
    def createSheetView(self, **kwargs):  # pragma: no cover
        return sheet_view.SheetView(**kwargs)
