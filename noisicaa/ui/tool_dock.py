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

# mypy: loose

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import flowlayout
from . import dock_widget
from . import tools
from . import ui_base

logger = logging.getLogger(__name__)


class ToolsDockWidget(ui_base.ProjectMixin, dock_widget.DockWidget):
    def __init__(self, **kwargs):
        super().__init__(
            identifier='tools',
            title="Tools",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self.__tool_box = None

        self.__group = QtWidgets.QButtonGroup()
        self.__group.buttonClicked.connect(self.__onButtonClicked)

        self.__main_area = QtWidgets.QWidget()
        self.__main_area.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setWidget(self.__main_area)

    def __onButtonClicked(self, button):
        assert self.__tool_box is not None
        tool_type = tools.ToolType(self.__group.id(button))
        self.__tool_box.setCurrentToolType(tool_type)

    def __onToolTypeChanged(self, tool_type):
        for button in self.__group.buttons():
            if self.__group.id(button) == tool_type.value:
                button.setChecked(True)

    def setCurrentToolBox(self, tool_box):
        logger.debug("Updating tool dock for tool_box=%s", type(tool_box).__name__)

        if self.__tool_box is not None:
            self.__tool_box.toolTypeChanged.disconnect(self.__onToolTypeChanged)
            self.__tool_box = None

        if tool_box is not None:
            self.__tool_box = tool_box
            self.__tool_box.toolTypeChanged.connect(self.__onToolTypeChanged)

        for button in self.__group.buttons():
            self.__group.removeButton(button)
        if self.__main_area.layout() is not None:
            QtWidgets.QWidget().setLayout(self.__main_area.layout())

        layout = flowlayout.FlowLayout(spacing=1)

        if self.__tool_box is not None:
            for tool in self.__tool_box.tools():
                button = QtWidgets.QToolButton()
                button.setIcon(QtGui.QIcon(tool.iconPath()))
                button.setIconSize(QtCore.QSize(32, 32))
                button.setAutoRaise(True)
                button.setCheckable(True)
                button.setChecked(tool.type == self.__tool_box.currentToolType())
                self.__group.addButton(button, tool.type.value)
                layout.addWidget(button)

        self.__main_area.setLayout(layout)
        layout.doLayout(self.__main_area.geometry(), False)
