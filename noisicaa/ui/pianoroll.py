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

import contextlib
import enum
import fractions
import logging
from typing import Any, Optional, Dict, List, Set, Tuple, Generator, Iterator, Sequence

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import sortedcontainers

from noisicaa import core
from noisicaa import audioproc
from noisicaa import value_types
from . import slots

logger = logging.getLogger(__name__)


class PianoKeys(slots.SlotContainer, QtWidgets.QWidget):
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)
    scrollable, setScrollable, scrollableChanged = slots.slot(bool, 'scrollable', default=False)

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

        self.__scrolling = False
        self.__prev_y = 0
        self.__active_keys = set()  # type: Set[int]

        self.yOffsetChanged.connect(lambda _: self.update())

    def gridHeight(self) -> int:
        return 128 * self.gridYSize() + 1

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

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if not self.scrollable():
            super().mousePressEvent(evt)
            return

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            self.__scrolling = True
            self.__prev_y = evt.pos().y()
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__scrolling:
            dy = evt.pos().y() - self.__prev_y
            self.__prev_y = evt.pos().y()
            self.setYOffset(
                max(0, min(self.gridHeight() - self.height(), self.yOffset() - dy)))
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__scrolling:
            self.__scrolling = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

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


class Mutation(object):
    def __init__(self, event_id: int, event: value_types.MidiEvent) -> None:
        self.event_id = event_id
        self.event = event

    def __str__(self) -> str:
        return '%s #%d %s' % (type(self).__name__, self.event_id, self.event)


class AddEvent(Mutation):
    pass


class RemoveEvent(Mutation):
    pass


class Interval(object):
    __slots__ = ['start_event', 'start_id', 'end_event', 'end_id', 'duration']

    def __init__(
            self, *,
            start_event: value_types.MidiEvent,
            start_id: int,
            end_event: value_types.MidiEvent = None,
            end_id: int = None,
            duration: audioproc.MusicalDuration = None) -> None:
        assert start_event.midi[0] & 0xf0 == 0x90
        self.start_event = start_event
        self.start_id = start_id
        if end_event is not None:
            assert end_event.midi[0] & 0xf0 == 0x80
            assert end_id is not None
            assert duration is None
            self.end_event = end_event
            self.end_id = end_id
            self.duration = self.end_event.time - self.start_event.time
        else:
            assert end_event is None
            assert end_id is None
            assert duration is not None
            self.end_event = None
            self.end_id = None
            self.duration = duration

    def __hash__(self) -> int:
        return self.start_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Interval) and other.start_id == self.start_id

    @property
    def is_note_on(self) -> bool:
        return self.start_event.midi[0] & 0xf0 == 0x90

    @property
    def is_note_off(self) -> bool:
        return self.start_event.midi[0] & 0xf0 == 0x80

    @property
    def channel(self) -> int:
        return self.start_event.midi[0] & 0x0f

    @property
    def pitch(self) -> int:
        return self.start_event.midi[1]

    @property
    def velocity(self) -> int:
        return self.start_event.midi[2]

    @property
    def start_time(self) -> audioproc.MusicalTime:
        return self.start_event.time

    @property
    def end_time(self) -> audioproc.MusicalTime:
        return self.start_event.time + self.duration


class PianoRollGrid(slots.SlotContainer, QtWidgets.QWidget):
    duration, setDuration, durationChanged = slots.slot(
        audioproc.MusicalDuration, 'duration', default=audioproc.MusicalDuration(8, 4))
    playbackPosition, setPlaybackPosition, playbackPositionChanged = slots.slot(
        audioproc.MusicalTime, 'playbackPosition', default=audioproc.MusicalTime(-1, 1))
    unfinishedNoteMode, setUnfinishedNoteMode, unfinishedNoteModeChanged = slots.slot(
        UnfinishedNoteMode, 'unfinishedNoteMode', default=UnfinishedNoteMode.ToEnd)
    xOffset, setXOffset, xOffsetChanged = slots.slot(int, 'xOffset', default=0)
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    widthChanged = QtCore.pyqtSignal(int)
    heightChanged = QtCore.pyqtSignal(int)
    gridWidthChanged = QtCore.pyqtSignal(int)
    gridHeightChanged = QtCore.pyqtSignal(int)
    gridXSize, setGridXSize, gridXSizeChanged = slots.slot(
        fractions.Fraction, 'gridXSize', default=fractions.Fraction(4*80))
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)
    readOnly, setReadOnly, readOnlyChanged = slots.slot(bool, 'readOnly', default=True)
    hoverNote, setHoverNote, hoverNoteChanged = slots.slot(int, 'hoverNote', default=-1)

    channel_base_colors = [
        QtGui.QColor(100, 100, 255),
        QtGui.QColor(100, 255, 100),
        QtGui.QColor(255, 100, 100),
        QtGui.QColor(100, 255, 255),
        QtGui.QColor(255, 255, 100),
        QtGui.QColor(255, 100, 255),
        QtGui.QColor(100, 180, 255),
        QtGui.QColor(180, 100, 255),
        QtGui.QColor(180, 255, 100),
        QtGui.QColor(100, 255, 180),
        QtGui.QColor(255, 100, 180),
        QtGui.QColor(255, 180, 100),
        QtGui.QColor(180, 180, 100),
        QtGui.QColor(180, 100, 180),
        QtGui.QColor(100, 180, 180),
        QtGui.QColor(180, 100, 180),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.mutations = core.Callback[Sequence[Mutation]]()

        self.__collected_mutations = None  # type: List[Mutation]

        self.__bg_color = QtGui.QColor(245, 245, 245)
        self.__black_key_color = QtGui.QColor(230, 230, 230)
        self.__grid_color = QtGui.QColor(200, 200, 200)
        self.__note_color = QtGui.QColor(100, 100, 255)
        self.__add_interval_color = QtGui.QColor(180, 180, 255)
        self.__selected_border1_color = QtGui.QColor(255, 255, 255)
        self.__selected_border2_color = QtGui.QColor(0, 0, 0)
        self.__playback_position_color = QtGui.QColor(0, 0, 0)

        self.__next_event_id = 0
        self.__events = {}  # type: Dict[int, value_types.MidiEvent]
        self.__sorted_events = sortedcontainers.SortedList()

        self.__selection = set()  # type: Set[Interval]

        self.__action = None  # type: str
        self.__interval_note = None  # type: int
        self.__interval_start_time = None  # type: audioproc.MusicalTime
        self.__interval_end_time = None  # type: audioproc.MusicalTime
        self.__click_pos = None  # type: QtCore.QPoint
        self.__move_delta_pitch = None  # type: int
        self.__move_delta_time = None  # type: audioproc.MusicalDuration
        self.__selection_pos1 = None  # type: QtCore.QPoint
        self.__selection_pos2 = None  # type: QtCore.QPoint

        self.setMinimumSize(100, 50)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMouseTracking(not self.readOnly())
        self.readOnlyChanged.connect(lambda _: self.setMouseTracking(not self.readOnly()))

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

    def __noteAt(self, y: int) -> int:
        row, offset = divmod(y, self.gridYSize())
        if 0 <= row <= 127 and self.gridYSize() <= 3 or offset != 0:
            return 127 - row
        return -1

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverNote(-1)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)
        if evt.size().width() != evt.oldSize().width():
            self.widthChanged.emit(evt.size().width())
        if evt.size().height() != evt.oldSize().height():
            self.heightChanged.emit(evt.size().height())

    def __intervals(self) -> Iterator[Interval]:
        active_pitches = {}  # type: Dict[Tuple[int, int], Tuple[value_types.MidiEvent, int]]
        for event, event_id in self.__sorted_events:
            if event.midi[0] & 0xf0 not in (0x80, 0x90):
                continue

            channel = event.midi[0] & 0x0f
            pitch = event.midi[1]
            if (channel, pitch) in active_pitches:
                start_event, start_event_id = active_pitches.pop((channel, pitch))
                if event.midi[0] & 0xf0 == 0x80:
                    yield Interval(
                        start_id=start_event_id,
                        start_event=start_event,
                        end_id=event_id,
                        end_event=event)
                else:
                    yield Interval(
                        start_id=start_event_id,
                        start_event=start_event,
                        duration=event.time - start_event.time)

            if event.midi[0] & 0xf0 == 0x90:
                active_pitches[(channel, pitch)] = (event, event_id)

        if self.unfinishedNoteMode() != UnfinishedNoteMode.Hide:
            if self.unfinishedNoteMode() == UnfinishedNoteMode.ToPlaybackPosition:
                end_time = self.playbackPosition()
            else:
                end_time = audioproc.MusicalTime(0, 1) + self.duration()

            for event, event_id in active_pitches.values():
                yield Interval(
                    start_id=event_id,
                    start_event=event,
                    duration=end_time - event.time)

    def __intervalAt(self, pitch: int, time: audioproc.MusicalTime) -> Optional[Interval]:
        for interval in self.__intervals():
            if interval.pitch == pitch and interval.start_time <= time < interval.end_time:
                return interval

        return None

    def __drawInterval(
            self,
            painter: QtGui.QPainter,
            channel: int, velocity: int, selected: int,
            x1: int, x2: int, y: int) -> None:
        w = x2 - x1
        h = self.gridYSize()
        if h > 3:
            y += 1
            h -= 1

        base_color = self.channel_base_colors[channel]
        base_color = base_color.darker(100 + (127 - velocity))

        if h > 3:
            if selected:
                painter.fillRect(x1 - 1, y - 1, w + 2, h + 2, self.__selected_border2_color)
            painter.fillRect(x1, y, w, h, base_color)

            if w > 3:
                if selected:
                    hi_color = self.__selected_border1_color
                    lo_color = self.__selected_border1_color
                else:
                    hi_color = base_color.lighter(130)
                    lo_color = base_color.darker(130)

                painter.fillRect(x1, y, w, 1, hi_color)
                painter.fillRect(x1, y, 1, h, hi_color)
                painter.fillRect(x1 + 1, y + h - 1, w - 1, 1, lo_color)
                painter.fillRect(x2 - 1, y + 1, 1, h - 1, lo_color)
        else:
            painter.fillRect(x1, y, x2 - x1, h, base_color)

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

            for interval in self.__intervals():
                if interval in self.__selection:
                    continue

                y = (127 - interval.pitch) * grid_y_size
                x1 = int(interval.start_time * grid_x_size)
                x2 = int(interval.end_time * grid_x_size)
                self.__drawInterval(
                    painter,
                    interval.channel, interval.velocity,
                    False,
                    x1, x2, y)

            for interval in self.__selection:
                pitch = interval.pitch
                start_time = interval.start_time
                end_time = interval.end_time

                if self.__action == 'move-selection':
                    pitch += self.__move_delta_pitch
                    if not 0 <= pitch <= 127:
                        continue
                    start_time += self.__move_delta_time
                    end_time += self.__move_delta_time

                y = (127 - pitch) * grid_y_size
                x1 = int(start_time * grid_x_size)
                x2 = int(end_time * grid_x_size)
                self.__drawInterval(
                    painter, interval.channel, interval.velocity, True, x1, x2, y)

            if self.__action == 'add-interval' and self.__interval_end_time is not None:
                assert self.__interval_start_time is not None
                assert self.__interval_end_time is not None
                start_time = self.__interval_start_time
                end_time = self.__interval_end_time
                if start_time > end_time:
                    start_time, end_time = end_time, start_time
                if start_time != end_time:
                    y = (127 - self.__interval_note) * grid_y_size
                    x1 = int(start_time * grid_x_size)
                    x2 = int(end_time * grid_x_size)
                    self.__drawInterval(painter, 0, 100, True, x1, x2, y)

            if self.__action == 'select-rect':
                x1 = min(self.__selection_pos1.x(), self.__selection_pos2.x())
                y1 = min(self.__selection_pos1.y(), self.__selection_pos2.y())
                x2 = max(self.__selection_pos1.x(), self.__selection_pos2.x())
                y2 = max(self.__selection_pos1.y(), self.__selection_pos2.y())

                w = x2 - x1 + 1
                h = y2 - y1 + 1
                painter.fillRect(x1, y1, w, 1, Qt.black)
                painter.fillRect(x1, y2, w, 1, Qt.black)
                painter.fillRect(x1, y1, 1, h, Qt.black)
                painter.fillRect(x2, y1, 1, h, Qt.black)
                if w > 2 and h > 2:
                    painter.fillRect(x1 + 1, y1 + 1, w - 2, h - 2, QtGui.QColor(200, 200, 255, 80))

            playback_position = self.playbackPosition()
            if playback_position.numerator >= 0:
                x = int(playback_position * grid_x_size)
                painter.fillRect(x, 0, 1, height, self.__playback_position_color)

        finally:
            painter.end()

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.readOnly():
            super().keyPressEvent(evt)
            return

        if self.__selection and evt.key() == Qt.Key_Delete and evt.modifiers() == Qt.NoModifier:
            intervals = set(self.__selection)
            self.__selection.clear()

            with self.__collect_mutations():
                for interval in intervals:
                    self.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.removeEvent(interval.end_id)

            evt.accept()
            return

        super().keyPressEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mousePressEvent(evt)
            return

        note = self.__noteAt(evt.pos().y() + self.yOffset())

        if evt.button() == Qt.LeftButton:
            if note >= 0:
                time = audioproc.MusicalTime((evt.pos().x() + self.xOffset()) / self.gridXSize())
                interval = self.__intervalAt(note, time)
                if interval is not None:
                    if (not evt.modifiers() & Qt.ControlModifier
                            and interval not in self.__selection):
                        self.__selection.clear()

                    if (evt.modifiers() & Qt.ControlModifier
                            and interval in self.__selection):
                        self.__selection.discard(interval)
                    else:
                        self.__selection.add(interval)

                else:
                    if not evt.modifiers() & Qt.ControlModifier:
                        self.__selection.clear()

            else:
                if not evt.modifiers() & Qt.ControlModifier:
                    self.__selection.clear()

            self.update()

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.ShiftModifier:
            self.__action = 'select-rect'
            self.__selection_pos1 = evt.pos()
            self.__selection_pos2 = evt.pos()
            evt.accept()
            return

        if (note >= 0
                and not self.__selection
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.__action = 'add-interval'
            self.__interval_note = note
            self.__interval_start_time = audioproc.MusicalTime(
                (evt.pos().x() + self.xOffset()) / self.gridXSize())
            self.__interval_end_time = self.__interval_start_time
            evt.accept()
            return

        if self.__selection and evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            self.__action = 'move-selection'
            self.__click_pos = evt.pos()
            self.__move_delta_pitch = 0
            self.__move_delta_time = audioproc.MusicalDuration(0, 1)
            evt.accept()
            return

        if note >= 0 and evt.button() == Qt.MiddleButton and evt.modifiers() == Qt.NoModifier:
            time = audioproc.MusicalTime((evt.pos().x() + self.xOffset()) / self.gridXSize())
            interval = self.__intervalAt(note, time)
            if interval is not None:
                self.__selection.discard(interval)
                with self.__collect_mutations():
                    self.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.removeEvent(interval.end_id)

                evt.accept()
                return

        if evt.button() == Qt.RightButton and self.__action == 'add-interval':
            self.__action = None
            self.update()
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mouseMoveEvent(evt)
            return

        if self.__action == 'add-interval':
            self.__interval_end_time = audioproc.MusicalTime(
                (evt.pos().x() + self.xOffset()) / self.gridXSize())
            self.update()
            evt.accept()
            return

        if self.__action == 'move-selection':
            delta = evt.pos() - self.__click_pos
            self.__move_delta_pitch = -int(delta.y() / self.gridYSize())
            self.__move_delta_time = audioproc.MusicalDuration(delta.x() / self.gridXSize())
            self.update()
            evt.accept()
            return

        if self.__action == 'select-rect':
            self.__selection_pos2 = evt.pos()

            x1 = min(self.__selection_pos1.x(), self.__selection_pos2.x())
            y1 = min(self.__selection_pos1.y(), self.__selection_pos2.y())
            x2 = max(self.__selection_pos1.x(), self.__selection_pos2.x())
            y2 = max(self.__selection_pos1.y(), self.__selection_pos2.y())

            pitch1 = 127 - (y2 + self.yOffset()) // self.gridYSize()
            time1 = audioproc.MusicalTime((x1 + self.xOffset()) / self.gridXSize())
            pitch2 = 127 - (y1 + self.yOffset()) // self.gridYSize()
            time2 = audioproc.MusicalTime((x2 + self.xOffset()) / self.gridXSize())

            self.__selection.clear()
            for interval in self.__intervals():
                if (pitch1 <= interval.pitch <= pitch2
                        and interval.start_time <= time2
                        and interval.end_time >= time1):
                    self.__selection.add(interval)

            self.update()
            evt.accept()
            return

        self.setHoverNote(self.__noteAt(evt.pos().y() + self.yOffset()))

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mouseReleaseEvent(evt)
            return

        if evt.button() == Qt.LeftButton and self.__action == 'add-interval':
            start_time = self.__interval_start_time
            end_time = self.__interval_end_time
            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if start_time != end_time:
                with self.__collect_mutations():
                    interval = self.addInterval(
                        0, self.__interval_note, 100,
                        start_time, end_time - start_time)
                    self.__selection = {interval}

            self.__action = None
            self.update()
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'move-selection':
            if (self.__move_delta_pitch != 0
                    or self.__move_delta_time != audioproc.MusicalDuration(0, 1)):
                intervals = set(self.__selection)
                self.__selection.clear()

                with self.__collect_mutations():
                    for interval in intervals:
                        self.removeEvent(interval.start_id)
                        if interval.end_event is not None:
                            self.removeEvent(interval.end_id)

                    segment_start_time = audioproc.MusicalTime(0, 1)
                    segment_end_time = audioproc.MusicalTime(0, 1) + self.duration()

                    for interval in intervals:
                        pitch = interval.pitch + self.__move_delta_pitch
                        if not 0 <= pitch <= 127:
                            continue

                        start_time = interval.start_time + self.__move_delta_time
                        end_time = interval.end_time + self.__move_delta_time
                        if end_time <= segment_start_time:
                            continue
                        if start_time >= segment_end_time:
                            continue

                        start_time = max(segment_start_time, start_time)
                        end_time = min(segment_end_time, end_time)
                        if start_time == end_time:
                            continue

                        interval = self.addInterval(
                            interval.channel, pitch, interval.velocity,
                            start_time, end_time - start_time)

                        self.__selection.add(interval)

            self.__action = None
            self.update()
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'select-rect':
            self.__action = None
            self.update()
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    @contextlib.contextmanager
    def __collect_mutations(self) -> Generator:
        self.__collected_mutations = []
        try:
            yield
            mutations = self.__collected_mutations
        finally:
            self.__collected_mutations = None

        if mutations:
            logger.info("Pianoroll mutations:")
            for mutation in mutations:
                logger.info("  %s", mutation)
            self.mutations.call(mutations)

    def clearEvents(self) -> None:
        self.__sorted_events.clear()
        self.__events.clear()
        self.update()

    def addInterval(
            self,
            channel: int, pitch: int, velocity: int,
            time: audioproc.MusicalTime,
            duration: audioproc.MusicalDuration
    ) -> Interval:
        start_time = time
        end_time = time + duration

        for interval in list(self.__intervals()):
            if interval.channel != channel or interval.pitch != pitch:
                continue
            if interval.start_time >= start_time and interval.end_time <= end_time:
                self.removeEvent(interval.start_id)
                if interval.end_event is not None:
                    self.removeEvent(interval.end_id)
            elif start_time > interval.start_time and end_time < interval.end_time:
                self.addEvent(value_types.MidiEvent(
                    start_time, bytes([0x80 | channel, pitch, 0])))
                self.addEvent(value_types.MidiEvent(
                    end_time, bytes([0x90 | channel, pitch, interval.velocity])))
            elif interval.start_time < start_time < interval.end_time:
                if interval.end_event is not None:
                    self.removeEvent(interval.end_id)
                self.addEvent(value_types.MidiEvent(
                    start_time, bytes([0x80 | channel, pitch, 0])))
            elif interval.start_time < end_time < interval.end_time:
                self.removeEvent(interval.start_id)
                self.addEvent(value_types.MidiEvent(
                    end_time, bytes([0x90 | channel, pitch, interval.velocity])))

        start_event = value_types.MidiEvent(
            start_time, bytes([0x90 | channel, pitch, velocity]))
        end_event = value_types.MidiEvent(
            end_time, bytes([0x80 | channel, pitch, 0]))
        start_id = self.addEvent(start_event)
        end_id = self.addEvent(end_event)
        interval = Interval(
            start_event=start_event,
            start_id=start_id,
            end_event=end_event,
            end_id=end_id)
        return interval

    def addEvent(self, event: value_types.MidiEvent) -> int:
        event_id = self.__next_event_id
        self.__next_event_id += 1
        self.__events[event_id] = event
        self.__sorted_events.add((event, event_id))
        if self.__collected_mutations is not None:
            self.__collected_mutations.append(AddEvent(event_id, event))
        self.update()
        return event_id

    def removeEvent(self, event_id: int) -> None:
        event = self.__events.pop(event_id)
        self.__sorted_events.remove((event, event_id))
        if self.__collected_mutations is not None:
            self.__collected_mutations.append(RemoveEvent(event_id, event))
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
