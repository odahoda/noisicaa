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
import typing
from typing import Any

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

if typing.TYPE_CHECKING:
    from . import editor as editor_lib

logger = logging.getLogger(__name__)


class BaseTrackEditor(
        time_view_mixin.TimeViewMixin,
        ui_base.ProjectMixin,
        core.AutoCleanupMixin,
        QtWidgets.QWidget):
    sizeChanged = QtCore.pyqtSignal(QtCore.QSize)
    currentToolChanged = QtCore.pyqtSignal(tools.ToolType)

    def __init__(
            self, *,
            track: music.Track,
            player_state: player_state_lib.PlayerState,
            editor: 'editor_lib.Editor',
            **kwargs: Any
    ) -> None:
        self.__auto_scroll = True

        super().__init__(parent=editor, **kwargs)

        self.setMouseTracking(True)

        self.__track = track
        self.__player_state = player_state
        self.__editor = editor

        self.__is_current = False
        self._bg_color = QtGui.QColor(255, 255, 255)

        self.scaleXChanged.connect(self.__scaleXChanged)
        self.__scaleXChanged(self.scaleX())

        self.__toolbox = self.createToolBox()

    @property
    def track(self) -> music.Track:
        return self.__track

    def setAutoScroll(self, auto_scroll: bool) -> None:
        self.__auto_scroll = auto_scroll

    def setXOffset(self, offset: int) -> int:
        dx = super().setXOffset(offset)
        if self.__auto_scroll:
            self.scroll(dx, 0)
        return dx

    def __scaleXChanged(self, scale_x: fractions.Fraction) -> None:
        self.updateSize()
        self.purgePaintCaches()
        self.update()

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), 0)

    def updateSize(self) -> None:
        pass

    def isCurrent(self) -> bool:
        return self.__is_current

    def setIsCurrent(self, is_current: bool) -> None:
        if is_current == self.__is_current:
            return

        self.__is_current = is_current

        if self.__is_current:
            self._bg_color = QtGui.QColor(240, 240, 255)
        else:
            self._bg_color = QtGui.QColor(255, 255, 255)

        self.update()

    def purgePaintCaches(self) -> None:
        pass

    def createToolBox(self) -> tools.ToolBox:
        raise NotImplementedError

    def toolBox(self) -> tools.ToolBox:
        return self.__toolbox

    def currentTool(self) -> tools.ToolBase:
        return self.__toolbox.currentTool()

    def currentToolType(self) -> tools.ToolType:
        return self.__toolbox.currentToolType()

    def setCurrentToolType(self, tool: tools.ToolType) -> None:
        self.__toolbox.setCurrentToolType(tool)

    def playerState(self) -> player_state_lib.PlayerState:
        return self.__player_state

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        pass

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        pass

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        self.sizeChanged.emit(evt.size())
        super().resizeEvent(evt)

    def _paint(self, painter: QtGui.QPainter, rect: QtCore.QRect) -> None:
        painter.setRenderHints(
            QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

        font = QtGui.QFont("Arial")
        font.setPixelSize(14)
        painter.setFont(font)
        pen = QtGui.QPen()
        pen.setColor(Qt.black)
        painter.setPen(pen)
        painter.drawText(
            QtCore.QRect(0, 0, self.width(), self.height()),
            Qt.AlignCenter,
            "%s.paintEvent() not implemented" % type(self).__name__)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self._bg_color)
            painter.translate(-self.xOffset(), 0)
            self._paint(painter, evt.rect().translated(self.xOffset(), 0))

        finally:
            painter.end()

    def _makeMouseEvent(self, evt: QtGui.QMouseEvent) -> QtGui.QMouseEvent:
        return QtGui.QMouseEvent(
            evt.type(),
            evt.localPos() + self.offset(),
            evt.windowPos(),
            evt.screenPos(),
            evt.button(),
            evt.buttons(),
            evt.modifiers())

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        evt = QtGui.QContextMenuEvent(
            evt.reason(),
            evt.pos() + self.offset(),
            evt.globalPos(),
            evt.modifiers())
        self.__toolbox.contextMenuEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__toolbox.mouseMoveEvent(self._makeMouseEvent(evt))

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__editor.setCurrentTrack(self.track)
        self.__toolbox.mousePressEvent(self._makeMouseEvent(evt))

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__toolbox.mouseReleaseEvent(self._makeMouseEvent(evt))

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__toolbox.mouseDoubleClickEvent(self._makeMouseEvent(evt))

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        evt = QtGui.QWheelEvent(
            evt.pos() + self.offset(),
            evt.globalPos(),
            evt.pixelDelta(),
            evt.angleDelta(),
            0,
            Qt.Horizontal,
            evt.buttons(),
            evt.modifiers(),
            evt.phase(),
            evt.source())
        self.__toolbox.wheelEvent(evt)

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        self.__toolbox.keyPressEvent(evt)

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        self.__toolbox.keyReleaseEvent(evt)
