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
import os.path
import enum

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from . import flowlayout
from . import dock_widget
from . import tools
from . import ui_base

logger = logging.getLogger(__name__)


class ToolsDockWidget(ui_base.ProjectMixin, dock_widget.DockWidget):
    toolChanged = QtCore.pyqtSignal(tools.Tool)

    def __init__(self, **kwargs):
        super().__init__(
            identifier='tools',
            title="Tools",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self.__supported_tools = { tools.Tool.POINTER }

        self.group = QtWidgets.QButtonGroup()
        self.layout = flowlayout.FlowLayout(spacing=1)

        self.addButton(tools.Tool.POINTER)

        self.addButton(tools.Tool.NOTE_WHOLE)
        self.addButton(tools.Tool.NOTE_HALF)
        self.addButton(tools.Tool.NOTE_QUARTER)
        self.addButton(tools.Tool.NOTE_8TH)
        self.addButton(tools.Tool.NOTE_16TH)
        self.addButton(tools.Tool.NOTE_32TH)

        self.addButton(tools.Tool.REST_WHOLE)
        self.addButton(tools.Tool.REST_HALF)
        self.addButton(tools.Tool.REST_QUARTER)
        self.addButton(tools.Tool.REST_8TH)
        self.addButton(tools.Tool.REST_16TH)
        self.addButton(tools.Tool.REST_32TH)

        self.addButton(tools.Tool.ACCIDENTAL_NATURAL)
        self.addButton(tools.Tool.ACCIDENTAL_SHARP)
        self.addButton(tools.Tool.ACCIDENTAL_FLAT)
        # double accidentals are not properly supported yet.
        #self.addButton(tools.Tool.ACCIDENTAL_DOUBLE_SHARP)
        #self.addButton(tools.Tool.ACCIDENTAL_DOUBLE_FLAT)

        self.addButton(tools.Tool.DURATION_DOT)
        self.addButton(tools.Tool.DURATION_TRIPLET)
        self.addButton(tools.Tool.DURATION_QUINTUPLET)

        current_tool = int(
            self.app.settings.value('tool/current', tools.Tool.NOTE_QUARTER))
        for button in self.group.buttons():
            if self.group.id(button) == current_tool:
                button.setChecked(True)

        self.group.buttonClicked.connect(self.onButtonClicked)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(self.layout)
        main_area.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setWidget(main_area)

    def addButton(self, tool):
        button = QtWidgets.QToolButton(
            icon=QtGui.QIcon(tool.icon_path),
            iconSize=QtCore.QSize(32, 32),
            checkable=True,
            autoRaise=True)
        self.group.addButton(button, tool)
        self.layout.addWidget(button)

    def onButtonClicked(self, button):
        tool_id = self.group.id(button)
        self.app.settings.setValue('tool/current', tool_id)
        self.toolChanged.emit(tools.Tool(tool_id))

    def currentTool(self):
        return tools.Tool(self.group.checkedId())

    def setCurrentTool(self, tool):
        for button in self.group.buttons():
            if self.group.id(button) == tool:
                button.setChecked(True)

    def supportedTools(self):
        return self.__supported_tools

    def setSupportedTools(self, supported_tools):
        logger.info(supported_tools)
        self.__supported_tools = set(supported_tools)
        for button in self.group.buttons():
            button.setVisible(
                self.group.id(button) in self.__supported_tools)

