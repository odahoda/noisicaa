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
import logging
import math
import typing
from typing import Any, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from . import slots

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class EngineState(slots.SlotContainer, QtCore.QObject):
    class State(enum.IntEnum):
        Setup = 0
        Cleanup = 1
        Running = 2
        Stopped = 3

    state, setState, stateChanged = slots.slot(
        State, 'state', default=State.Stopped)
    currentLoad, setCurrentLoad, currentLoadChanged = slots.slot(
        float, 'currentLoad', default=0.0)
    loadHistoryChanged = QtCore.pyqtSignal()

    HISTORY_LENGTH = 1000

    def __init__(self, parent: QtCore.QObject, **kwargs: Any) -> None:
        super().__init__(parent=parent, **kwargs)

        self.__history = [None] * self.HISTORY_LENGTH  # type: List[float]
        self.__latest_values = []  # type: List[float]
        self.currentLoadChanged.connect(self.__latest_values.append)

        self.__timer = QtCore.QTimer(self)
        self.__timer.setInterval(1000 // 25)
        self.__timer.timeout.connect(self.__updateHistory)
        self.__timer.start()

    def updateState(self, msg: audioproc.EngineStateChange) -> None:
        self.setState({
            audioproc.EngineStateChange.SETUP: self.State.Setup,
            audioproc.EngineStateChange.CLEANUP: self.State.Cleanup,
            audioproc.EngineStateChange.RUNNING: self.State.Running,
            audioproc.EngineStateChange.STOPPED: self.State.Stopped,
        }[msg.state])

    def updateLoad(self, msg: audioproc.EngineLoad) -> None:
        self.setCurrentLoad(msg.load)

    def loadHistory(self, num_ticks: int) -> List[float]:
        num_ticks = min(num_ticks, self.HISTORY_LENGTH)
        return self.__history[-num_ticks:]

    def __updateHistory(self) -> None:
        if self.__latest_values:
            self.__history.append(max(self.__latest_values))
            self.__latest_values.clear()
        elif self.state() == self.State.Running:
            self.__history.append(self.currentLoad())
        else:
            self.__history.append(None)
        if len(self.__history) > self.HISTORY_LENGTH:
            del self.__history[:-self.HISTORY_LENGTH]
        self.loadHistoryChanged.emit()


class LoadHistory(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, engine_state: EngineState) -> None:
        super().__init__(parent)

        self.__font = QtGui.QFont(self.font())
        self.__font.setPixelSize(12)

        self.__engine_state = engine_state
        self.__engine_state.loadHistoryChanged.connect(self.update)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)

        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0))

        history = self.__engine_state.loadHistory(max(25, self.width() // 2))
        x = self.width() - 2
        for value in reversed(history):
            if value is not None:
                value = max(0.0, min(value, 1.0))
                vh = int(self.height() * value)
                painter.fillRect(
                    x, self.height() - vh, 2, vh,
                    QtGui.QColor(int(255 * value), 255 - int(255 * value), 0))
            x -= 2

        if self.width() > 50 and self.height() > 16:
            last_second = [v for v in history[-25:] if v is not None]
            if len(last_second) > 5:
                avg = sum(last_second) / len(last_second)
                stddev = math.sqrt(sum((v - avg) ** 2 for v in last_second) / len(last_second))

                painter.setPen(Qt.white)
                painter.setFont(self.__font)
                painter.drawText(
                    4, 1, self.width() - 4, self.height() - 1,
                    Qt.AlignTop,
                    "%d\u00b1%d%%" % (100 * avg, 100 * stddev))

        return super().paintEvent(evt)
