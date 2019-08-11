#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import enum
import functools
import logging
import os.path
from typing import Any

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from noisicaa.ui import ui_base

logger = logging.getLogger(__name__)


class Tool(enum.Enum):
    SELECT = 'select'
    INSERT = 'insert'


class Toolbox(ui_base.ProjectMixin, QtWidgets.QWidget):
    toolChanged = QtCore.pyqtSignal(Tool)
    resetViewTriggered = QtCore.pyqtSignal()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        icon_size = QtCore.QSize(32, 32)

        self.__select_tool_action = QtWidgets.QAction("Selection tool", self)
        self.__select_tool_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-select.svg')))
        self.__select_tool_action.setCheckable(True)
        self.__select_tool_action.triggered.connect(functools.partial(self.setTool, Tool.SELECT))

        self.__select_tool_button = QtWidgets.QToolButton(self)
        self.__select_tool_button.setAutoRaise(True)
        self.__select_tool_button.setIconSize(icon_size)
        self.__select_tool_button.setDefaultAction(self.__select_tool_action)

        self.__insert_tool_action = QtWidgets.QAction("Insert tool", self)
        self.__insert_tool_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'list-add.svg')))
        self.__insert_tool_action.setCheckable(True)
        self.__insert_tool_action.triggered.connect(functools.partial(self.setTool, Tool.INSERT))

        self.__insert_tool_button = QtWidgets.QToolButton(self)
        self.__insert_tool_button.setAutoRaise(True)
        self.__insert_tool_button.setIconSize(icon_size)
        self.__insert_tool_button.setDefaultAction(self.__insert_tool_action)

        self.__reset_view_action = QtWidgets.QAction("Reset view", self)
        self.__reset_view_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'zoom-original.svg')))
        self.__reset_view_action.triggered.connect(self.resetViewTriggered.emit)

        self.__reset_view_button = QtWidgets.QToolButton(self)
        self.__reset_view_button.setAutoRaise(True)
        self.__reset_view_button.setIconSize(icon_size)
        self.__reset_view_button.setDefaultAction(self.__reset_view_action)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self.__select_tool_button)
        layout.addWidget(self.__insert_tool_button)
        layout.addSpacing(8)
        layout.addWidget(self.__reset_view_button)
        layout.addStretch(1)
        self.setLayout(layout)

        self.__tool_actions = {
            Tool.SELECT: self.__select_tool_action,
            Tool.INSERT: self.__insert_tool_action,
        }

        self.__current_tool = Tool.SELECT

        for tool, action in self.__tool_actions.items():
            action.setChecked(tool == self.__current_tool)

    def setTool(self, tool: Tool) -> None:
        if tool == self.__current_tool:
            return

        self.__current_tool = tool
        for tool, action in self.__tool_actions.items():
            action.setChecked(tool == self.__current_tool)
        self.toolChanged.emit(self.__current_tool)
