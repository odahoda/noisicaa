#!/usr/bin/python

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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import sortedcontainers

from noisicaa import audioproc
from . import slots


class MidiEvent(object):
    def __init__(self, time: audioproc.MusicalTime, midi: bytes) -> None:
        self.time = time
        self.midi = midi


class UnfinishedNoteMode(enum.Enum):
    Hide = 1
    ToPlaybackPosition = 2
    ToEnd = 3


class PianoRollGrid(slots.SlotContainer, QtWidgets.QWidget):
    duration, setDuration, durationChanged = slots.slot(
        audioproc.MusicalDuration, 'duration', default=audioproc.MusicalDuration(8, 4))
    playbackPosition, setPlaybackPosition, playbackPositionChanged = slots.slot(
        audioproc.MusicalTime, 'playbackPosition', default=audioproc.MusicalTime(0, 1))
    unfinishedNoteMode, setUnfinishedNoteMode, unfinishedNoteModeChanged = slots.slot(
        UnfinishedNoteMode, 'unfinishedNoteMode', default=UnfinishedNoteMode.ToEnd)
    xOffset, setXOffset, xOffsetChanged = slots.slot(int, 'xOffset', default=0)
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridWidthChanged = QtCore.pyqtSignal(int)
    gridHeightChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__grid_y_size = 15
        self.__grid_x_size = 4 * 80

        self.__bg_color = QtGui.QColor(245, 245, 245)
        self.__grid_color = QtGui.QColor(200, 200, 200)
        self.__note_color = QtGui.QColor(100, 100, 255)
        self.__playback_position_color = QtGui.QColor(0, 0, 0)

        self.__events = sortedcontainers.SortedList(
            key=lambda event: (event.time, event.midi[0] & 0xf0))

        self.setMinimumSize(100, 50)

        self.playbackPositionChanged.connect(lambda _: self.update())
        self.durationChanged.connect(lambda _: self.update())
        self.unfinishedNoteModeChanged.connect(lambda _: self.update())
        self.xOffsetChanged.connect(lambda _: self.update())
        self.yOffsetChanged.connect(lambda _: self.update())

        self.durationChanged.connect(lambda _: self.gridWidthChanged.emit(self.gridWidth()))

    def gridWidth(self) -> int:
        return int(self.duration() * self.__grid_x_size) + 1

    def gridHeight(self) -> int:
        return 128 * self.__grid_y_size + 1

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self.__bg_color)

            width = self.gridWidth()
            height = self.gridHeight()

            painter.translate(QtCore.QPoint(-self.xOffset(), -self.yOffset()))

            if self.__grid_y_size > 3:
                font = QtGui.QFont()
                font.setPixelSize(max(6, min(self.__grid_y_size - 4, 16)))
                fmetrics = QtGui.QFontMetrics(font)
                painter.setFont(font)
                painter.setPen(Qt.black)

                y = 0
                for n in reversed(range(0, 128)):
                    painter.fillRect(0, y, width, 1, self.__grid_color)
                    if self.__grid_y_size > 10:
                        painter.drawText(2, y + fmetrics.ascent(), '%d' % n)
                    y += self.__grid_y_size
                painter.fillRect(0, y, width, 1, self.__grid_color)

            t = audioproc.MusicalTime(0, 1)
            while t <= audioproc.MusicalTime(0, 1) + self.duration():
                x = int(t * self.__grid_x_size)
                painter.fillRect(x, 0, 1, height, self.__grid_color)
                t += audioproc.MusicalDuration(1, 4)

            active_notes = {}  # type: Dict[int, audioproc.MusicalTime]
            for event in self.__events:
                if event.midi[0] & 0xf0 in (0x80, 0x90):
                    pitch = event.midi[1]
                    if pitch in active_notes:
                        y = (127 - pitch) * self.__grid_y_size
                        x1 = int(active_notes[pitch] * self.__grid_x_size)
                        x2 = int(event.time * self.__grid_x_size)
                        painter.fillRect(
                            x1, y + 1, x2 - x1, self.__grid_y_size - 1, self.__note_color)
                        del active_notes[pitch]

                    if event.midi[0] & 0xf0 == 0x90:
                        active_notes[pitch] = event.time

            if self.unfinishedNoteMode() != UnfinishedNoteMode.Hide:
                if self.unfinishedNoteMode() == UnfinishedNoteMode.ToPlaybackPosition:
                    end_time = self.playbackPosition()
                else:
                    end_time = audioproc.MusicalTime(0, 1) + self.duration()

                x2 = int(end_time * self.__grid_x_size)
                for pitch, time in active_notes.items():
                    if time <= end_time:
                        y = (127 - pitch) * self.__grid_y_size
                        x1 = int(time * self.__grid_x_size)
                        painter.fillRect(
                            x1, y + 1, x2 - x1, self.__grid_y_size - 1, self.__note_color)

            x = int(self.playbackPosition() * self.__grid_x_size)
            painter.fillRect(x, 0, 1, height, self.__playback_position_color)

        finally:
            painter.end()

    def clearEvents(self) -> None:
        self.__events.clear()
        self.update()

    def addEvent(self, time: audioproc.MusicalTime, midi: bytes) -> None:
        self.__events.add(MidiEvent(time, midi))
        self.update()


class PianoRoll(slots.SlotContainer, QtWidgets.QWidget):
    duration, setDuration, durationChanged = slots.slot(
        audioproc.MusicalDuration, 'duration', default=audioproc.MusicalDuration(8, 4))
    playbackPosition, setPlaybackPosition, playbackPositionChanged = slots.slot(
        audioproc.MusicalTime, 'playbackPosition', default=audioproc.MusicalTime(0, 1))
    unfinishedNoteMode, setUnfinishedNoteMode, unfinishedNoteModeChanged = slots.slot(
        UnfinishedNoteMode, 'unfinishedNoteMode', default=UnfinishedNoteMode.ToEnd)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__vscrollbar = QtWidgets.QScrollBar()
        self.__vscrollbar.setOrientation(Qt.Vertical)

        self.__hscrollbar = QtWidgets.QScrollBar()
        self.__hscrollbar.setOrientation(Qt.Horizontal)

        self.__grid = PianoRollGrid()
        self.durationChanged.connect(self.__grid.setDuration)
        self.playbackPositionChanged.connect(self.__grid.setPlaybackPosition)
        self.unfinishedNoteModeChanged.connect(self.__grid.setUnfinishedNoteMode)

        self.__hscrollbar.setPageStep(self.__grid.gridWidth())
        self.__grid.gridWidthChanged.connect(self.__hscrollbar.setPageStep)
        self.__hscrollbar.valueChanged.connect(self.__grid.setXOffset)

        self.__vscrollbar.setPageStep(self.__grid.gridHeight())
        self.__grid.gridHeightChanged.connect(self.__vscrollbar.setPageStep)
        self.__vscrollbar.valueChanged.connect(self.__grid.setYOffset)

        l2 = QtWidgets.QVBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(0)
        l2.addWidget(self.__grid)
        l2.addWidget(self.__hscrollbar)

        l1 = QtWidgets.QHBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(0)
        l1.addWidget(self.__vscrollbar)
        l1.addLayout(l2)
        self.setLayout(l1)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)
        self.__hscrollbar.setRange(
            0, max(0, self.__grid.gridWidth() - self.__grid.size().width()))
        self.__vscrollbar.setRange(
            0, max(0, self.__grid.gridHeight() - self.__grid.size().height()))

    def clearEvents(self) -> None:
        self.__grid.clearEvents()

    def addEvent(self, time: audioproc.MusicalTime, midi: bytes) -> None:
        self.__grid.addEvent(time, midi)
