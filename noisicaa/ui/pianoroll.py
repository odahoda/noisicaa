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
import logging
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import sortedcontainers

from noisicaa import audioproc
from noisicaa import value_types
from . import slots

logger = logging.getLogger(__name__)


class PianoKeys(slots.SlotContainer, QtWidgets.QWidget):
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setFixedWidth(40)

        self.__bg_color = QtGui.QColor(255, 255, 255)
        self.__sep_color = QtGui.QColor(0, 0, 0)
        self.__label_color = QtGui.QColor(0, 0, 0)
        self.__white_key_body_color = QtGui.QColor(230, 230, 230)
        self.__white_key_edge1_color = QtGui.QColor(255, 255, 255)
        self.__white_key_edge2_color = QtGui.QColor(160, 160, 160)
        self.__black_key_body_color = QtGui.QColor(60, 60, 60)
        self.__black_key_edge1_color = QtGui.QColor(120, 120, 120)
        self.__black_key_edge2_color = QtGui.QColor(40, 40, 40)
        self.__active_key_body_color = QtGui.QColor(160, 160, 255)
        self.__active_key_edge1_color = QtGui.QColor(200, 200, 255)
        self.__active_key_edge2_color = QtGui.QColor(100, 100, 160)

        self.__active_keys = set()

        self.yOffsetChanged.connect(lambda _: self.update())

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self.__bg_color)

            grid_y_size = self.gridYSize()
            width = self.width()
            bkwidth = 5 * (width - 2) // 8
            height = 128 * grid_y_size + 1

            painter.translate(QtCore.QPoint(0, -self.yOffset()))

            if grid_y_size > 3:
                font = QtGui.QFont()
                font.setPixelSize(max(6, min(grid_y_size - 4, 16)))
                fmetrics = QtGui.QFontMetrics(font)
                painter.setFont(font)
                painter.setPen(self.__label_color)

                for o in range(0, 12):
                    y = (128 - 12 * o) * grid_y_size

                    ky2 = y
                    for kn, ky1 in (
                            (0, y - 5 * grid_y_size // 3),
                            (2, y - 10 * grid_y_size // 3),
                            (4, y - 5 * grid_y_size),
                            (5, y - 5 * grid_y_size - 7 * grid_y_size // 4),
                            (7, y - 5 * grid_y_size - 14 * grid_y_size // 4),
                            (9, y - 5 * grid_y_size - 21 * grid_y_size // 4),
                            (11, y - 5 * grid_y_size - 28 * grid_y_size // 4)):
                        n = 12 * o + kn
                        if n in self.__active_keys:
                            edge1_color = self.__active_key_edge1_color
                            edge2_color = self.__active_key_edge2_color
                            body_color = self.__active_key_body_color
                        else:
                            edge1_color = self.__white_key_edge1_color
                            edge2_color = self.__white_key_edge2_color
                            body_color = self.__white_key_body_color
                        painter.fillRect(0, ky1, width, 1, self.__sep_color)
                        painter.fillRect(1, ky1 + 1, width - 2, 1, edge1_color)
                        painter.fillRect(1, ky1 + 2, 1, ky2 - ky1 - 2, edge1_color)
                        painter.fillRect(width - 2, ky1 + 2, 1, ky2 - ky1 - 3, edge2_color)
                        painter.fillRect(2, ky2 - 1, width - 3, 1, edge2_color)
                        painter.fillRect(2, ky1 + 2, width - 4, ky2 - ky1 - 3, body_color)
                        ky2 = ky1

                    for kn, kt, kb in ((1, 2, 1), (3, 4, 3), (6, 7, 6), (8, 9, 8), (10, 11, 10)):
                        n = 12 * o + kn
                        ky1 = y - kt * grid_y_size
                        ky2 = y - kb * grid_y_size
                        if n in self.__active_keys:
                            edge1_color = self.__active_key_edge1_color
                            edge2_color = self.__active_key_edge2_color
                            body_color = self.__active_key_body_color
                        else:
                            edge1_color = self.__black_key_edge1_color
                            edge2_color = self.__black_key_edge2_color
                            body_color = self.__black_key_body_color
                        painter.fillRect(1, ky1, bkwidth + 1, 1, self.__sep_color)
                        painter.fillRect(1, ky2, bkwidth + 1, 1, self.__sep_color)
                        painter.fillRect(bkwidth + 1, ky1, 1, ky2 - ky1 + 1, self.__sep_color)
                        painter.fillRect(1, ky1 + 1, bkwidth, 1, edge1_color)
                        painter.fillRect(1, ky1 + 2, 1, ky2 - ky1 - 2, edge1_color)
                        painter.fillRect(bkwidth, ky1 + 2, 1, ky2 - ky1 - 2, edge2_color)
                        painter.fillRect(2, ky2 - 1, bkwidth - 1, 1, edge2_color)
                        painter.fillRect(2, ky1 + 2, bkwidth - 2, ky2 - ky1 - 3, body_color)

                    if grid_y_size > 10:
                        painter.drawText(8, y - fmetrics.descent(), 'C%d' % (o - 2))

            painter.fillRect(0, 0, width, 1, self.__sep_color)
            painter.fillRect(0, height - 1, width, 1, self.__sep_color)
            painter.fillRect(0, 0, 1, height, self.__sep_color)
            painter.fillRect(width - 1, 0, 1, height, self.__sep_color)

        finally:
            painter.end()

    def noteOn(self, note: int) -> None:
        self.__active_keys.add(note)
        self.update()

    def noteOff(self, note: int) -> None:
        self.__active_keys.discard(note)
        self.update()


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
    widthChanged = QtCore.pyqtSignal(int)
    heightChanged = QtCore.pyqtSignal(int)
    gridWidthChanged = QtCore.pyqtSignal(int)
    gridHeightChanged = QtCore.pyqtSignal(int)
    gridXSize, setGridXSize, gridXSizeChanged = slots.slot(int, 'gridXSize', default=4*80)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__bg_color = QtGui.QColor(245, 245, 245)
        self.__black_key_color = QtGui.QColor(230, 230, 230)
        self.__grid_color = QtGui.QColor(200, 200, 200)
        self.__note_color = QtGui.QColor(100, 100, 255)
        self.__playback_position_color = QtGui.QColor(0, 0, 0)

        self.__next_event_id = 0
        self.__events = {}  # Dict[int, value_types.MidiEvent]
        self.__sorted_events = sortedcontainers.SortedList()

        self.setMinimumSize(100, 50)

        self.playbackPositionChanged.connect(lambda _: self.update())
        self.durationChanged.connect(lambda _: self.update())
        self.unfinishedNoteModeChanged.connect(lambda _: self.update())
        self.xOffsetChanged.connect(lambda _: self.update())
        self.yOffsetChanged.connect(lambda _: self.update())

        self.durationChanged.connect(lambda _: self.gridWidthChanged.emit(self.gridWidth()))

    def gridWidth(self) -> int:
        return int(self.duration() * self.gridXSize()) + 1

    def gridHeight(self) -> int:
        return 128 * self.gridYSize() + 1

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.gridWidth(), 24 * self.gridYSize())

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)
        if evt.size().width() != evt.oldSize().width():
            self.widthChanged.emit(evt.size().width())
        if evt.size().height() != evt.oldSize().height():
            self.heightChanged.emit(evt.size().height())

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self.__bg_color)

            width = self.gridWidth()
            height = self.gridHeight()
            grid_x_size = self.gridXSize()
            grid_y_size = self.gridYSize()

            painter.translate(QtCore.QPoint(-self.xOffset(), -self.yOffset()))

            if grid_y_size > 3:
                y = 0
                for n in reversed(range(0, 128)):
                    painter.fillRect(0, y, width, 1, self.__grid_color)
                    if n % 12 in {1, 3, 6, 8, 10}:
                        painter.fillRect(0, y + 1, width, grid_y_size - 1, self.__black_key_color)
                    y += grid_y_size
                painter.fillRect(0, y, width, 1, self.__grid_color)

            t = audioproc.MusicalTime(0, 1)
            while t <= audioproc.MusicalTime(0, 1) + self.duration():
                x = int(t * grid_x_size)
                painter.fillRect(x, 0, 1, height, self.__grid_color)
                t += audioproc.MusicalDuration(1, 4)

            active_notes = {}  # type: Dict[int, audioproc.MusicalTime]
            for event, _ in self.__sorted_events:
                if event.midi[0] & 0xf0 in (0x80, 0x90):
                    pitch = event.midi[1]
                    if pitch in active_notes:
                        y = (127 - pitch) * grid_y_size
                        x1 = int(active_notes[pitch] * grid_x_size)
                        x2 = int(event.time * grid_x_size)
                        painter.fillRect(
                            x1, y + 1, x2 - x1, grid_y_size - 1, self.__note_color)
                        del active_notes[pitch]

                    if event.midi[0] & 0xf0 == 0x90:
                        active_notes[pitch] = event.time

            if self.unfinishedNoteMode() != UnfinishedNoteMode.Hide:
                if self.unfinishedNoteMode() == UnfinishedNoteMode.ToPlaybackPosition:
                    end_time = self.playbackPosition()
                else:
                    end_time = audioproc.MusicalTime(0, 1) + self.duration()

                x2 = int(end_time * grid_x_size)
                for pitch, time in active_notes.items():
                    if time <= end_time:
                        y = (127 - pitch) * grid_y_size
                        x1 = int(time * grid_x_size)
                        painter.fillRect(
                            x1, y + 1, x2 - x1, grid_y_size - 1, self.__note_color)

            x = int(self.playbackPosition() * grid_x_size)
            painter.fillRect(x, 0, 1, height, self.__playback_position_color)

        finally:
            painter.end()

    def clearEvents(self) -> None:
        self.__sorted_events.clear()
        self.__events.clear()
        self.update()

    def addEvent(self, event: value_types.MidiEvent) -> int:
        event_id = self.__next_event_id
        self.__next_event_id += 1
        self.__events[event_id] = event
        self.__sorted_events.add((event, event_id))
        self.update()
        return event_id

    def removeEvent(self, event_id: int) -> None:
        event = self.__events.pop(event_id)
        self.__sorted_events.remove((event, event_id))
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

        self.__keys = PianoKeys()

        self.__grid = PianoRollGrid()
        self.durationChanged.connect(self.__grid.setDuration)
        self.playbackPositionChanged.connect(self.__grid.setPlaybackPosition)
        self.unfinishedNoteModeChanged.connect(self.__grid.setUnfinishedNoteMode)

        self.__grid.gridWidthChanged.connect(lambda _: self.__updateHScrollBar())
        self.__grid.widthChanged.connect(lambda _: self.__updateHScrollBar())
        self.__hscrollbar.valueChanged.connect(self.__grid.setXOffset)

        self.__grid.gridHeightChanged.connect(lambda _: self.__updateVScrollBar())
        self.__grid.heightChanged.connect(lambda _: self.__updateVScrollBar())
        self.__vscrollbar.valueChanged.connect(self.__grid.setYOffset)
        self.__vscrollbar.valueChanged.connect(self.__keys.setYOffset)

        l1 = QtWidgets.QGridLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(1)
        l1.addWidget(self.__vscrollbar, 0, 2, 1, 1)
        l1.addWidget(self.__keys, 0, 0, 1, 1)
        l1.addWidget(self.__grid, 0, 1, 1, 1)
        l1.addWidget(self.__hscrollbar, 1, 1, 1, 1)
        self.setLayout(l1)

    def __updateHScrollBar(self) -> None:
        self.__hscrollbar.setMaximum(
            max(0, self.__grid.gridWidth() - self.__grid.width()))
        self.__hscrollbar.setPageStep(self.__grid.gridWidth())

    def __updateVScrollBar(self) -> None:
        self.__vscrollbar.setMaximum(
            max(0, self.__grid.gridHeight() - self.__grid.height()))
        self.__vscrollbar.setPageStep(self.__grid.gridHeight())

    def connectSlots(self, slot_connections: slots.SlotConnectionManager, name: str) -> None:
        slot_connections.connect(
            name + ':xoffset',
            self.__hscrollbar.setValue,
            self.__hscrollbar.valueChanged,
            0)
        slot_connections.connect(
            name + ':yoffset',
            self.__vscrollbar.setValue,
            self.__vscrollbar.valueChanged,
            max(0, self.__grid.gridHeight() - self.__grid.height()) // 2)

    def disconnectSlots(self, slot_connections: slots.SlotConnectionManager, name: str) -> None:
        slot_connections.disconnect(name + ':xoffset')
        slot_connections.disconnect(name + ':yoffset')

    def clearEvents(self) -> None:
        self.__grid.clearEvents()

    def addEvent(self, event: value_types.MidiEvent) -> int:
        return self.__grid.addEvent(event)

    def removeEvent(self, event_id: int) -> None:
        self.__grid.removeEvent(event_id)

    def noteOn(self, note: int) -> None:
        self.__keys.noteOn(note)

    def noteOff(self, note: int) -> None:
        self.__keys.noteOff(note)
