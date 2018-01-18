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

import logging
import enum
import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa import constants
from . import ui_base


logger = logging.getLogger(__name__)


class ToolGroup(enum.IntEnum):
    # pylint: disable=bad-whitespace

    ARRANGE = 1
    EDIT    = 2


class ToolType(enum.IntEnum):
    # pylint: disable=bad-whitespace

    NOTE_WHOLE   = 100
    NOTE_HALF    = 101
    NOTE_QUARTER = 102
    NOTE_8TH     = 103
    NOTE_16TH    = 104
    NOTE_32TH    = 105

    REST_WHOLE   = 200
    REST_HALF    = 201
    REST_QUARTER = 202
    REST_8TH     = 203
    REST_16TH    = 204
    REST_32TH    = 205

    ACCIDENTAL_NATURAL      = 300
    ACCIDENTAL_FLAT         = 301
    ACCIDENTAL_SHARP        = 302
    ACCIDENTAL_DOUBLE_FLAT  = 303
    ACCIDENTAL_DOUBLE_SHARP = 304

    DURATION_DOT        = 400
    DURATION_TRIPLET    = 401
    DURATION_QUINTUPLET = 402

    ARRANGE_MEASURES = 500
    EDIT_BEATS = 501
    EDIT_CONTROL_POINTS = 502
    EDIT_SAMPLES = 503

    @property
    def is_note(self):
        return ToolType.NOTE_WHOLE <= self <= ToolType.NOTE_32TH

    @property
    def is_rest(self):
        return ToolType.REST_WHOLE <= self <= ToolType.REST_32TH

    @property
    def is_accidental(self):
        return ToolType.ACCIDENTAL_NATURAL <= self <= ToolType.ACCIDENTAL_DOUBLE_SHARP

    @property
    def is_duration(self):
        return ToolType.DURATION_DOT <= self <= ToolType.DURATION_QUINTUPLET


class ToolBase(ui_base.ProjectMixin, QtCore.QObject):
    cursorChanged = QtCore.pyqtSignal(QtGui.QCursor)

    def __init__(self, *, type, group, **kwargs):
        super().__init__(**kwargs)
        self.type = type
        self.group = group

    def iconName(self):
        raise NotImplementedError

    def iconPath(self):
        return os.path.join(constants.DATA_DIR, 'icons', '%s.svg' % self.iconName())

    def cursor(self):
        return QtGui.QCursor(Qt.ArrowCursor)

    def _mouseMoveEvent(self, target, evt):
        self.mouseMoveEvent(target, evt)

    def mouseMoveEvent(self, target, evt):
        pass

    def _mousePressEvent(self, target, evt):
        self.mousePressEvent(target, evt)

    def mousePressEvent(self, target, evt):
        pass

    def _mouseReleaseEvent(self, target, evt):
        self.mouseReleaseEvent(target, evt)

    def mouseReleaseEvent(self, target, evt):
        pass

    def _mouseDoubleClickEvent(self, target, evt):
        self.mouseDoubleClickEvent(target, evt)

    def mouseDoubleClickEvent(self, target, evt):
        self.mousePressEvent(target, evt)

    def _wheelEvent(self, target, evt):
        self.wheelEvent(target, evt)

    def wheelEvent(self, target, evt):
        pass

    def _keyPressEvent(self, target, evt):
        self.keyPressEvent(target, evt)

    def keyPressEvent(self, target, evt):
        pass

    def _keyReleaseEvent(self, target, evt):
        self.keyReleaseEvent(target, evt)

    def keyReleaseEvent(self, target, evt):
        pass


class ToolBox(ui_base.ProjectMixin, QtCore.QObject):
    toolTypeChanged = QtCore.pyqtSignal(ToolType)
    currentToolChanged = QtCore.pyqtSignal(ToolBase)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__tools = []
        self.__groups = []
        self.__tool_map = {}
        self.__current_tool_in_group = {}
        self.__current_tool = None
        self.__previous_tool = None

    def tools(self):
        return iter(self.__tools)

    def addTool(self, tool):
        assert tool.type not in self.__tool_map

        self.__tools.append(tool)
        if tool.group not in self.__groups:
            self.__groups.append(tool.group)
        self.__tool_map[tool.type] = tool
        if self.__current_tool is None:
            self.__current_tool = tool
        if tool.group not in self.__current_tool_in_group:
            self.__current_tool_in_group[tool.group] = tool.type

    def currentTool(self):
        return self.__current_tool

    def currentToolType(self):
        return self.__current_tool.type

    def setCurrentToolType(self, type):
        if type != self.__current_tool.type:
            self.__previous_tool = self.__current_tool
            self.__current_tool = self.__tool_map[type]
            self.__current_tool_in_group[self.__current_tool.group] = type
            self.toolTypeChanged.emit(self.__current_tool.type)
            self.currentToolChanged.emit(self.__current_tool)

    def setPreviousTool(self):
        if self.__previous_tool is not None:
            if self.__previous_tool is not self.__current_tool:
                self.__current_tool = self.__previous_tool
                self.toolTypeChanged.emit(self.__current_tool.type)
                self.currentToolChanged.emit(self.__current_tool)
            self.__previous_tool = None

    def mouseMoveEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._mouseMoveEvent(target, evt)

    def mousePressEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._mousePressEvent(target, evt)

    def mouseReleaseEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._mouseReleaseEvent(target, evt)

    def mouseDoubleClickEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._mouseDoubleClickEvent(target, evt)

    def wheelEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._wheelEvent(target, evt)

    def keyPressEvent(self, target, evt):
        assert self.__current_tool is not None

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.KeypadModifier
                and evt.key() == Qt.Key_Plus):
            group_idx = self.__groups.index(self.__current_tool.group)
            group_idx = (group_idx + 1) % len(self.__groups)
            group = self.__groups[group_idx]
            tool = self.__current_tool_in_group[group]
            self.setCurrentToolType(tool)
            evt.accept()
            return

        return self.__current_tool._keyPressEvent(target, evt)

    def keyReleaseEvent(self, target, evt):
        assert self.__current_tool is not None
        return self.__current_tool._keyReleaseEvent(target, evt)
