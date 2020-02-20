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
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import player_state as player_state_lib
from . import time_view_mixin

logger = logging.getLogger(__name__)


class TimeLine(
        time_view_mixin.ContinuousTimeMixin,
        time_view_mixin.TimeViewMixin,
        ui_base.ProjectMixin,
        QtWidgets.QWidget):
    def __init__(
            self, *,
            player_state: 'player_state_lib.PlayerState',
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)

        self.__player_state = player_state
        self.__player_id = None  # type: str
        self.__move_time = False
        self.__old_player_state = None  # type: bool

        self.__player_state.currentTimeChanged.connect(self.onCurrentTimeChanged)
        self.__player_state.loopStartTimeChanged.connect(lambda _: self.update())
        self.__player_state.loopEndTimeChanged.connect(lambda _: self.update())

        self.__duration_listener = self.project.duration_changed.add(self.onDurationChanged)

        self.scaleXChanged.connect(lambda _: self.update())
        self.additionalXOffsetChanged.connect(lambda _: self.update())

    def setPlayerID(self, player_id: str) -> None:
        self.__player_id = player_id

    def onSetLoopStart(self, loop_start_time: audioproc.MusicalTime) -> None:
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_start_time=loop_start_time.to_proto())))

    def onSetLoopEnd(self, loop_end_time: audioproc.MusicalTime) -> None:
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_end_time=loop_end_time.to_proto())))

    def onClearLoop(self) -> None:
        pass

    def onCurrentTimeChanged(self, current_time: audioproc.MusicalTime) -> None:
        if self.isVisible():
            x = self.timeToX(self.__player_state.currentTime())

            left = self.xOffset() + 1 * self.width() // 5
            right = self.xOffset() + 4 * self.width() // 5
            if x < left:
                self.setXOffset(max(0, x - 1 * self.width() // 5))
            elif x > right:
                self.setXOffset(x - 4 * self.width() // 5)

        self.update()

    def onDurationChanged(self, change: music.PropertyValueChange[float]) -> None:
        self.update()

    def setXOffset(self, offset: int) -> int:
        dx = super().setXOffset(offset)
        self.scroll(dx, 0)
        return dx

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if (self.__player_id is not None
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.__move_time = True
            self.__old_player_state = self.__player_state.playing()
            x = evt.pos().x() + self.xOffset()
            current_time = self.xToTime(x)
            self.call_async(
                self.project_client.update_player_state(
                    self.__player_id,
                    audioproc.PlayerState(playing=False)))
            self.__player_state.setTimeMode(player_state_lib.TimeMode.Manual)
            self.__player_state.setCurrentTime(current_time)
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__move_time:
            x = evt.pos().x() + self.xOffset()
            current_time = min(self.xToTime(x), self.projectEndTime())
            if self.shouldSnap(evt):
                current_time = self.snapTime(current_time)
            self.__player_state.setCurrentTime(current_time)
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__move_time and evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            self.__move_time = False
            x = evt.pos().x() + self.xOffset()
            current_time = min(self.xToTime(x), self.projectEndTime())
            if self.shouldSnap(evt):
                current_time = self.snapTime(current_time)
            self.call_async(
                self.project_client.update_player_state(
                    self.__player_id,
                    audioproc.PlayerState(
                        playing=self.__old_player_state,
                        current_time=current_time.to_proto())))
            self.__player_state.setTimeMode(player_state_lib.TimeMode.Follow)
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu()

        if not self.__player_state.playing() and self.__player_state.currentTime() is not None:
            set_loop_start = QtWidgets.QAction("Set loop start", menu)
            set_loop_start.triggered.connect(
                lambda _: self.onSetLoopStart(self.__player_state.currentTime()))
            menu.addAction(set_loop_start)

            set_loop_end = QtWidgets.QAction("Set loop end", menu)
            set_loop_end.triggered.connect(
                lambda _: self.onSetLoopEnd(self.__player_state.currentTime()))
            menu.addAction(set_loop_end)

        clear_loop = QtWidgets.QAction("Clear loop", menu)
        clear_loop.triggered.connect(lambda _: self.onClearLoop())
        menu.addAction(clear_loop)

        if not menu.isEmpty():
            menu.exec_(evt.globalPos())
            evt.accept()
            return

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), Qt.white)

            painter.translate(-self.xOffset(), 0)

            self.renderTimeGrid(
                painter, evt.rect().translated(self.xOffset(), 0), show_numbers=True)

            # loop markers
            loop_start_time = self.__player_state.loopStartTime()
            if loop_start_time is not None:
                x = self.timeToX(loop_start_time)
                painter.setBrush(Qt.black)
                painter.setPen(Qt.NoPen)
                polygon = QtGui.QPolygon()
                polygon.append(QtCore.QPoint(x, 0))
                polygon.append(QtCore.QPoint(x + 7, 0))
                polygon.append(QtCore.QPoint(x + 2, 5))
                polygon.append(QtCore.QPoint(x + 2, self.height() - 5))
                polygon.append(QtCore.QPoint(x + 7, self.height()))
                polygon.append(QtCore.QPoint(x, self.height()))
                painter.drawPolygon(polygon)

            loop_end_time = self.__player_state.loopEndTime()
            if loop_end_time is not None:
                x = self.timeToX(loop_end_time)
                painter.setBrush(Qt.black)
                painter.setPen(Qt.NoPen)
                polygon = QtGui.QPolygon()
                polygon.append(QtCore.QPoint(x - 6, 0))
                polygon.append(QtCore.QPoint(x + 2, 0))
                polygon.append(QtCore.QPoint(x + 2, self.height()))
                polygon.append(QtCore.QPoint(x - 6, self.height()))
                polygon.append(QtCore.QPoint(x, self.height() - 6))
                polygon.append(QtCore.QPoint(x, 6))
                painter.drawPolygon(polygon)

            # playback time
            x = self.timeToX(self.__player_state.currentTime())
            painter.fillRect(x, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

        finally:
            painter.end()
