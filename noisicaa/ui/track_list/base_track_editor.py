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

import fractions
import logging
from typing import Any, Type

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import player_state as player_state_lib
from . import time_view_mixin
from . import tools

# TODO: These would create cyclic import dependencies.
Editor = Any


logger = logging.getLogger(__name__)


# TODO: fold into BaseTrackEditor
class _Base(
        time_view_mixin.ScaledTimeMixin,
        ui_base.ProjectMixin,
        core.AutoCleanupMixin,
        QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)
    sizeChanged = QtCore.pyqtSignal(QtCore.QSize)

    def __init__(self, *, track: music.Track, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__track = track
        self.__view_top_left = QtCore.QPoint()
        self.__is_current = False

        self.__size = QtCore.QSize()

        self.scaleXChanged.connect(self.__scaleXChanged)
        self.contentWidthChanged.connect(self.setWidth)

    @property
    def track(self) -> music.Track:
        return self.__track

    def __scaleXChanged(self, scale_x: fractions.Fraction) -> None:
        self.updateSize()
        self.purgePaintCaches()
        self.rectChanged.emit(self.viewRect())

    def width(self) -> int:
        return self.__size.width()

    def setWidth(self, width: int) -> None:
        self.setSize(QtCore.QSize(width, self.height()))

    def height(self) -> int:
        return self.__size.height()

    def setHeight(self, height: int) -> None:
        self.setSize(QtCore.QSize(self.width(), height))

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.__size)

    def setSize(self, size: QtCore.QSize) -> None:
        if size != self.__size:
            self.__size = QtCore.QSize(size)
            self.sizeChanged.emit(self.__size)

    def updateSize(self) -> None:
        pass

    def viewTopLeft(self) -> QtCore.QPoint:
        return self.__view_top_left

    def viewLeft(self) -> int:
        return self.__view_top_left.x()

    def viewTop(self) -> int:
        return self.__view_top_left.y()

    def setViewTopLeft(self, top_left: QtCore.QPoint) -> None:
        self.__view_top_left = QtCore.QPoint(top_left)

    def viewRect(self) -> QtCore.QRect:
        return QtCore.QRect(self.__view_top_left, self.size())

    def isCurrent(self) -> bool:
        return self.__is_current

    def setIsCurrent(self, is_current: bool) -> None:
        if is_current != self.__is_current:
            self.__is_current = is_current
            #self.rectChanged.emit(self.viewRect())

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        pass

    def purgePaintCaches(self) -> None:
        pass

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        if self.isCurrent():
            painter.fillRect(paint_rect, QtGui.QColor(240, 240, 255))
        else:
            painter.fillRect(paint_rect, Qt.white)

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        pass  # pragma: no coverage

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        pass  # pragma: no coverage

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        pass  # pragma: no coverage

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass  # pragma: no coverage

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass  # pragma: no coverage


class BaseTrackEditor(_Base):
    currentToolChanged = QtCore.pyqtSignal(tools.ToolType)

    toolBoxClass = None  # type: Type[tools.ToolBox]

    def __init__(
            self, *,
            player_state: player_state_lib.PlayerState, editor: Editor, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__player_state = player_state
        self.__editor = editor

    def toolBox(self) -> tools.ToolBox:
        tool_box = self.__editor.currentToolBox()
        assert isinstance(tool_box, self.toolBoxClass)
        return tool_box

    def currentTool(self) -> tools.ToolBase:
        return self.toolBox().currentTool()

    def currentToolType(self) -> tools.ToolType:
        return self.toolBox().currentToolType()

    def toolBoxMatches(self) -> bool:
        return isinstance(self.__editor.currentToolBox(), self.toolBoxClass)

    def playerState(self) -> player_state_lib.PlayerState:
        return self.__player_state

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseMoveEvent(self, evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mousePressEvent(self, evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseReleaseEvent(self, evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseDoubleClickEvent(self, evt)

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().wheelEvent(self, evt)

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().keyPressEvent(self, evt)

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().keyReleaseEvent(self, evt)
