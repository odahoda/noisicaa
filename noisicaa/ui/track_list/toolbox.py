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

import logging
from typing import Any, Optional

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.ui import flowlayout
from noisicaa.ui import ui_base
from . import tools

logger = logging.getLogger(__name__)


class Toolbox(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__tool_box = None  # type: Optional[tools.ToolBox]

        self.__group = QtWidgets.QButtonGroup()
        self.__group.buttonClicked.connect(self.__onButtonClicked)

    def __onButtonClicked(self, button: QtWidgets.QAbstractButton) -> None:
        assert self.__tool_box is not None
        tool_type = tools.ToolType(self.__group.id(button))
        self.__tool_box.setCurrentToolType(tool_type)

    def __onToolTypeChanged(self, tool_type: tools.ToolType) -> None:
        for button in self.__group.buttons():
            if self.__group.id(button) == tool_type.value:
                button.setChecked(True)

    def setCurrentToolBox(self, tool_box: Optional[tools.ToolBox]) -> None:
        logger.info("Using tool_box=%s", type(tool_box).__name__)

        if self.__tool_box is not None:
            self.__tool_box.toolTypeChanged.disconnect(self.__onToolTypeChanged)
            self.__tool_box = None

        if tool_box is not None:
            self.__tool_box = tool_box
            self.__tool_box.toolTypeChanged.connect(self.__onToolTypeChanged)

        for button in self.__group.buttons():
            self.__group.removeButton(button)
        if self.layout() is not None:
            QtWidgets.QWidget().setLayout(self.layout())

        layout = flowlayout.FlowLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

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

        self.setLayout(layout)
        layout.doLayout(self.geometry(), False)
