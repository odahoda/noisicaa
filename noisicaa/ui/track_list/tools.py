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
import enum
import functools
import os.path
import typing
from typing import Any, List, Dict, Iterator, Type

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from noisicaa.ui import ui_base

if typing.TYPE_CHECKING:
    from . import base_track_editor

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
    PIANOROLL_ARRANGE_SEGMENTS = 504
    PIANOROLL_EDIT_EVENTS = 505
    PIANOROLL_SELECT_EVENTS = 506
    PIANOROLL_EDIT_VELOCITY = 507

    @property
    def is_note(self) -> bool:
        return ToolType.NOTE_WHOLE <= self <= ToolType.NOTE_32TH

    @property
    def is_rest(self) -> bool:
        return ToolType.REST_WHOLE <= self <= ToolType.REST_32TH

    @property
    def is_accidental(self) -> bool:
        return ToolType.ACCIDENTAL_NATURAL <= self <= ToolType.ACCIDENTAL_DOUBLE_SHARP

    @property
    def is_duration(self) -> bool:
        return ToolType.DURATION_DOT <= self <= ToolType.DURATION_QUINTUPLET


class ToolBase(ui_base.ProjectMixin, QtCore.QObject):
    cursorChanged = QtCore.pyqtSignal(QtGui.QCursor)

    def __init__(
            self, *,
            track: 'base_track_editor.BaseTrackEditor',
            type: ToolType,  # pylint: disable=redefined-builtin
            group: ToolGroup,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.track = track
        self.type = type
        self.group = group

    def iconName(self) -> str:
        raise NotImplementedError

    def iconPath(self) -> str:
        path = os.path.join(constants.DATA_DIR, 'icons', '%s.svg' % self.iconName())
        if os.path.isfile(path):
            return path
        logger.error("Icon %s not found", path)
        return os.path.join(constants.DATA_DIR, 'icons', 'error.svg')

    def cursor(self) -> QtGui.QCursor:
        return QtGui.QCursor(Qt.ArrowCursor)

    def keySequence(self) -> QtGui.QKeySequence:
        return None

    def activated(self) -> None:
        pass

    def deactivated(self) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.mousePressEvent(evt)

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        pass

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass


class ToolBox(ui_base.ProjectMixin, QtCore.QObject):
    toolTypeChanged = QtCore.pyqtSignal(ToolType)
    currentToolChanged = QtCore.pyqtSignal(ToolBase)

    def __init__(self, track: 'base_track_editor.BaseTrackEditor', **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.track = track

        self.__tools = []  # type: List[ToolBase]
        self.__groups = []  # type: List[ToolGroup]
        self.__tool_map = {}  # type: Dict[ToolType, ToolBase]
        self.__current_tool_in_group = {}  # type: Dict[ToolGroup, ToolType]
        self.__current_tool = None  # type: ToolBase
        self.__previous_tool = None  # type: ToolBase

    def tools(self) -> Iterator[ToolBase]:
        return iter(self.__tools)

    def addTool(self, cls: Type[ToolBase], **kwargs: Any) -> None:
        tool = cls(track=self.track, context=self.context, **kwargs)
        assert tool.type not in self.__tool_map

        if tool.keySequence() is not None:
            action = QtWidgets.QAction(self.track)
            action.setShortcut(tool.keySequence())
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.triggered.connect(
                functools.partial(self.setCurrentToolType, tool.type))
            self.track.addAction(action)

        self.__tools.append(tool)
        if tool.group not in self.__groups:
            self.__groups.append(tool.group)
        self.__tool_map[tool.type] = tool
        if self.__current_tool is None:
            self.__current_tool = tool
            self.__current_tool.activated()
        if tool.group not in self.__current_tool_in_group:
            self.__current_tool_in_group[tool.group] = tool.type

    def currentTool(self) -> ToolBase:
        return self.__current_tool

    def currentToolType(self) -> ToolType:
        return self.__current_tool.type

    def setCurrentToolType(self, type: ToolType) -> None:  # pylint: disable=redefined-builtin
        if type != self.__current_tool.type:
            self.__previous_tool = self.__current_tool
            self.__current_tool.deactivated()
            self.__current_tool = self.__tool_map[type]
            self.__current_tool.activated()
            self.__current_tool_in_group[self.__current_tool.group] = type
            self.toolTypeChanged.emit(self.__current_tool.type)
            self.currentToolChanged.emit(self.__current_tool)

    def setPreviousTool(self) -> None:
        if self.__previous_tool is not None:
            if self.__previous_tool is not self.__current_tool:
                self.__current_tool.deactivated()
                self.__current_tool = self.__previous_tool
                self.__current_tool.activated()
                self.toolTypeChanged.emit(self.__current_tool.type)
                self.currentToolChanged.emit(self.__current_tool)
            self.__previous_tool = None

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.mouseMoveEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.mousePressEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.mouseReleaseEvent(evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.mouseDoubleClickEvent(evt)

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.wheelEvent(evt)

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.__current_tool is not None:
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

            self.__current_tool.keyPressEvent(evt)

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.__current_tool is not None:
            self.__current_tool.keyReleaseEvent(evt)
