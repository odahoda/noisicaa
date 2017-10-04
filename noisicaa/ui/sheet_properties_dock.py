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

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import dock_widget
from . import ui_base

logger = logging.getLogger(__name__)


class SheetProperties(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, *, sheet, **kwargs):
        super().__init__(**kwargs)

        self.__sheet = sheet

        self.__listeners = []

        self.__name = QtWidgets.QLineEdit(self)
        self.__name.textEdited.connect(self.onNameEdited)
        self.__name.setText(self.__sheet.name)
        self.__listeners.append(
            self.__sheet.listeners.add('name', self.onNameChanged))

        self.__bpm = QtWidgets.QSpinBox(self)
        self.__bpm.setRange(1, 1000)
        self.__bpm.valueChanged.connect(self.onBPMEdited)
        self.__bpm.setValue(self.__sheet.bpm)
        self.__listeners.append(
            self.__sheet.listeners.add('bpm', self.onBPMChanged))

        self.__form_layout = QtWidgets.QFormLayout(spacing=1)
        self.__form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.__form_layout.addRow("Name", self.__name)
        self.__form_layout.addRow("BPM", self.__bpm)

        self.setLayout(self.__form_layout)

    def cleanup(self):
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    def onNameChanged(self, old_name, new_name):
        self.__name.setText(new_name)

    def onNameEdited(self, name):
        if name != self.__sheet.name:
            self.send_command_async(
                self.__sheet.id, 'UpdateSheetProperties', name=name)

    def onBPMChanged(self, old_bpm, new_bpm):
        self.__bpm.setValue(new_bpm)

    def onBPMEdited(self, bpm):
        if bpm != self.__sheet.bpm:
            self.send_command_async(
                self.__sheet.id, 'UpdateSheetProperties', bpm=bpm)


class SheetPropertiesDockWidget(ui_base.ProjectMixin, dock_widget.DockWidget):
    def __init__(self, **kwargs):
        super().__init__(
            identifier='sheet-properties',
            title="Sheet Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self.__sheet = None

    def setSheet(self, sheet):
        if sheet is self.__sheet:
            return

        self.__sheet = sheet
        if self.__sheet is None:
            if self.main_widget is not None:
                self.main_widget.cleanup()
            self.setWidget(None)

        else:
            self.setWidget(SheetProperties(
                sheet=self.__sheet, **self.context))
