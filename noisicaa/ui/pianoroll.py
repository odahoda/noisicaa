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

    def noteOn(self, pitch: int) -> None:
        self.__active_keys.add(pitch)
        self.update()

    def noteOff(self, pitch: int) -> None:
        self.__active_keys.discard(pitch)
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


class AbstractInterval(object):
    @property
    def channel(self) -> int:
        raise NotImplementedError

    @property
    def pitch(self) -> int:
        raise NotImplementedError

    @property
    def velocity(self) -> int:
        raise NotImplementedError

    @property
    def start_time(self) -> audioproc.MusicalTime:
        raise NotImplementedError

    @property
    def end_time(self) -> audioproc.MusicalTime:
        raise NotImplementedError

    @property
    def duration(self) -> audioproc.MusicalDuration:
        raise NotImplementedError


class Interval(AbstractInterval):
    __slots__ = ['start_event', 'start_id', 'end_event', 'end_id', '__duration']

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
            self.__duration = self.end_event.time - self.start_event.time
        else:
            assert end_event is None
            assert end_id is None
            assert duration is not None
            self.end_event = None
            self.end_id = None
            self.__duration = duration

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
        return self.start_event.time + self.__duration

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.__duration


class TempInterval(AbstractInterval):
    def __init__(
            self, *,
            channel: int, pitch: int, velocity: int,
            start_time: audioproc.MusicalTime, end_time: audioproc.MusicalTime
    ) -> None:
        self.__channel = channel
        self.__pitch = pitch
        self.__velocity = velocity
        self.__start_time = start_time
        self.__end_time = end_time

    @property
    def channel(self) -> int:
        return self.__channel

    @property
    def pitch(self) -> int:
        return self.__pitch

    @property
    def velocity(self) -> int:
        return self.__velocity

    @property
    def start_time(self) -> audioproc.MusicalTime:
        return self.__start_time

    @property
    def end_time(self) -> audioproc.MusicalTime:
        return self.__end_time

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.__end_time - self.__start_time


class State(object):
    def __init__(self, *, grid: 'PianoRollGrid') -> None:
        self.grid = grid

    def intervals(self) -> Iterator[Tuple[AbstractInterval, bool]]:
        selected_intervals = []  # type: List[Interval]
        for interval in self.grid.intervals():
            if self.grid.isSelected(interval):
                selected_intervals.append(interval)
                continue

            yield interval, False

        for interval in selected_intervals:
            yield interval, True

    def paintOverlay(self, painter: QtGui.QPainter) -> None:
        pass

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass


class DefaultState(State):
    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if (self.grid.numSelected() > 0
                and evt.key() == Qt.Key_Delete
                and evt.modifiers() == Qt.NoModifier):
            intervals = self.grid.selection()
            self.grid.clearSelection()

            with self.grid.collect_mutations():
                for interval in intervals:
                    self.grid.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.grid.removeEvent(interval.end_id)

            evt.accept()

        if (self.grid.numSelected() > 0
                and evt.key() in (Qt.Key_Up, Qt.Key_Down)
                and evt.modifiers() in (Qt.NoModifier, Qt.ShiftModifier)):
            if evt.key() == Qt.Key_Up:
                delta_pitch = 1
            else:
                delta_pitch = -1

            if evt.modifiers() == Qt.ShiftModifier:
                delta_pitch *= 12

            intervals = self.grid.selection()
            self.grid.clearSelection()

            with self.grid.collect_mutations():
                for interval in intervals:
                    self.grid.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.grid.removeEvent(interval.end_id)

                for interval in intervals:
                    pitch = interval.pitch + delta_pitch
                    if not 0 <= pitch <= 127:
                        continue

                    interval = self.grid.addInterval(
                        interval.channel, pitch, interval.velocity,
                        interval.start_time, interval.duration)

                    self.grid.addToSelection(interval)

            evt.accept()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pitch = self.grid.pitchAt(evt.pos().y() + self.grid.yOffset())
        time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())

        if evt.button() == Qt.LeftButton:
            if pitch >= 0:
                interval = self.grid.intervalAt(pitch, time)
                if interval is not None:
                    is_selected = self.grid.isSelected(interval)
                    if not evt.modifiers() & Qt.ControlModifier and not is_selected:
                        self.grid.clearSelection()

                    if evt.modifiers() & Qt.ControlModifier and self.grid.isSelected(interval):
                        self.grid.removeFromSelection(interval)
                    else:
                        self.grid.addToSelection(interval)

                else:
                    if not evt.modifiers() & Qt.ControlModifier:
                        self.grid.clearSelection()

            else:
                if not evt.modifiers() & Qt.ControlModifier:
                    self.grid.clearSelection()

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.ControlModifier:
            self.grid.setCurrentState(SelectRectState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if (self.grid.numSelected() <= 1
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            grid_x_size = self.grid.gridXSize()
            for interval in self.grid.intervals(pitch=pitch):
                start_x = int(interval.start_time * grid_x_size) - self.grid.xOffset()
                end_x = int(interval.end_time * grid_x_size) - self.grid.xOffset()
                if max(end_x - 3, start_x) <= evt.pos().x() <= end_x + 3:
                    self.grid.setCurrentState(ResizeIntervalState(
                        grid=self.grid,
                        evt=evt,
                        interval=interval,
                        side=ResizeIntervalState.END))
                    self.grid.clearSelection()
                    evt.accept()
                    return
                if start_x - 3 <= evt.pos().x() <= min(start_x + 3, end_x):
                    self.grid.setCurrentState(ResizeIntervalState(
                        grid=self.grid,
                        evt=evt,
                        interval=interval,
                        side=ResizeIntervalState.START))
                    self.grid.clearSelection()
                    evt.accept()
                    return

        if (pitch >= 0
                and self.grid.numSelected() == 0
                and evt.button() == Qt.LeftButton
                and evt.modifiers() in (Qt.NoModifier, Qt.ShiftModifier)):
            self.grid.setCurrentState(AddIntervalState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if (self.grid.numSelected() > 0
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.grid.setCurrentState(MoveSelectionState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if pitch >= 0 and evt.button() == Qt.MiddleButton and evt.modifiers() == Qt.NoModifier:
            interval = self.grid.intervalAt(pitch, time)
            if interval is not None:
                self.grid.removeFromSelection(interval)
                with self.grid.collect_mutations():
                    self.grid.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.grid.removeEvent(interval.end_id)

                evt.accept()
                return

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pitch = self.grid.pitchAt(evt.pos().y() + self.grid.yOffset())

        self.grid.setHoverPitch(pitch)

        cursor = None

        if self.grid.numSelected() <= 1:
            grid_x_size = self.grid.gridXSize()
            for interval in self.grid.intervals(pitch=pitch):
                start_x = int(interval.start_time * grid_x_size) - self.grid.xOffset()
                end_x = int(interval.end_time * grid_x_size) - self.grid.xOffset()
                if max(end_x - 3, start_x) <= evt.pos().x() <= end_x + 3:
                    cursor = Qt.SizeHorCursor
                    break
                if start_x - 3 <= evt.pos().x() <= min(start_x + 3, end_x):
                    cursor = Qt.SizeHorCursor
                    break
                if start_x <= evt.pos().x() <= end_x:
                    cursor = Qt.OpenHandCursor
                    break

        if cursor is not None:
            self.grid.setCursor(cursor)
        else:
            self.grid.unsetCursor()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass


class AddIntervalState(State):
    def __init__(self, evt: QtGui.QMouseEvent, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitch = self.grid.pitchAt(evt.pos().y() + self.grid.yOffset())
        self.start_time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())
        if self.grid.shouldSnap(evt):
            self.start_time = self.grid.snapTime(self.start_time)
        self.end_time = self.start_time

        self.grid.playNote.emit(self.pitch)

    def intervals(self) -> Iterator[Tuple[AbstractInterval, bool]]:
        yield from super().intervals()

        start_time = self.start_time
        end_time = self.end_time
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        if start_time != end_time:
            interval = TempInterval(
                channel=0,
                pitch=self.pitch,
                velocity=100,
                start_time=start_time,
                end_time=end_time)
            yield interval, True

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.end_time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())
        if self.grid.shouldSnap(evt):
            self.end_time = self.grid.snapTime(self.end_time)
        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            start_time = self.start_time
            end_time = self.end_time
            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if start_time != end_time:
                with self.grid.collect_mutations():
                    interval = self.grid.addInterval(
                        0, self.pitch, 100,
                        start_time, end_time - start_time)
                self.grid.clearSelection()
                self.grid.addToSelection(interval)

            self.grid.playNote.emit(-1)

            self.grid.resetCurrentState()
            evt.accept()


class SelectRectState(State):
    def __init__(self, evt: QtGui.QMouseEvent, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pos1 = evt.pos() + self.grid.offset()
        self.pos2 = evt.pos() + self.grid.offset()

    def rect(self) -> QtCore.QRect:
        x1 = min(self.pos1.x(), self.pos2.x())
        y1 = min(self.pos1.y(), self.pos2.y())
        x2 = max(self.pos1.x(), self.pos2.x())
        y2 = max(self.pos1.y(), self.pos2.y())
        return QtCore.QRect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)

    def paintOverlay(self, painter: QtGui.QPainter) -> None:
        rect = self.rect()

        painter.fillRect(rect.left(), rect.top(), rect.width(), 1, Qt.black)
        painter.fillRect(rect.left(), rect.bottom(), rect.width(), 1, Qt.black)
        painter.fillRect(rect.left(), rect.top(), 1, rect.height(), Qt.black)
        painter.fillRect(rect.right(), rect.top(), 1, rect.height(), Qt.black)
        if rect.width() > 2 and rect.height() > 2:
            painter.fillRect(rect.adjusted(1, 1, -1, -1), QtGui.QColor(200, 200, 255, 80))

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.pos2 = evt.pos() + self.grid.offset()

        rect = self.rect()

        pitch1 = self.grid.pitchAt(rect.bottom())
        time1 = self.grid.timeAt(rect.left())
        pitch2 = self.grid.pitchAt(rect.top())
        time2 = self.grid.timeAt(rect.right())

        self.grid.clearSelection()
        for interval in self.grid.intervals():
            if (pitch1 <= interval.pitch <= pitch2
                    and interval.start_time <= time2
                    and interval.end_time >= time1):
                self.grid.addToSelection(interval)

        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.grid.resetCurrentState()
            evt.accept()


class ResizeIntervalState(State):
    START = 1
    END = 2

    def __init__(
            self,
            evt: QtGui.QMouseEvent, interval: Interval, side: int,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        start_x = int(interval.start_time * self.grid.gridXSize()) - self.grid.xOffset()
        end_x = int(interval.end_time * self.grid.gridXSize()) - self.grid.xOffset()

        self.side = side
        self.interval = interval

        if side == ResizeIntervalState.START:
            self.click_offset = evt.pos().x() - start_x
            self.time = interval.start_time
            self.time_limit = audioproc.MusicalTime(
                (end_x - 1 + self.grid.xOffset()) / self.grid.gridXSize())
        else:
            self.click_offset = evt.pos().x() - end_x
            self.time = interval.end_time
            self.time_limit = audioproc.MusicalTime(
                (start_x + 1 + self.grid.xOffset()) / self.grid.gridXSize())

    def intervals(self) -> Iterator[Tuple[AbstractInterval, bool]]:
        for interval, selected in super().intervals():
            if interval == self.interval:
                if self.side == ResizeIntervalState.START:
                    start_time = self.time
                    end_time = interval.end_time
                else:
                    start_time = interval.start_time
                    end_time = self.time

                interval = TempInterval(
                    channel=interval.channel,
                    pitch=interval.pitch,
                    velocity=interval.velocity,
                    start_time=start_time,
                    end_time=end_time)
                yield interval, selected

            else:
                yield interval, selected

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.side == ResizeIntervalState.START:
            time = self.grid.timeAt(evt.pos().x() + self.click_offset + self.grid.xOffset())
            if self.grid.shouldSnap(evt):
                time = self.grid.snapTime(time)
            self.time = min(self.time_limit, time)

        else:
            time = self.grid.timeAt(evt.pos().x() + self.click_offset + self.grid.xOffset())
            if self.grid.shouldSnap(evt):
                time = self.grid.snapTime(time)
            self.time = max(self.time_limit, time)

        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            if self.side == ResizeIntervalState.START:
                if self.time != self.interval.start_time:
                    with self.grid.collect_mutations():
                        self.grid.removeEvent(self.interval.start_id)
                        if self.interval.end_event is not None:
                            self.grid.removeEvent(self.interval.end_id)

                        self.grid.addInterval(
                            self.interval.channel,
                            self.interval.pitch,
                            self.interval.velocity,
                            self.time,
                            self.interval.end_time - self.time)

            else:
                if self.time != self.interval.end_time:
                    with self.grid.collect_mutations():
                        self.grid.removeEvent(self.interval.start_id)
                        if self.interval.end_event is not None:
                            self.grid.removeEvent(self.interval.end_id)

                        self.grid.addInterval(
                            self.interval.channel,
                            self.interval.pitch,
                            self.interval.velocity,
                            self.interval.start_time,
                            self.time - self.interval.start_time)

            self.grid.resetCurrentState()
            evt.accept()


class MoveSelectionState(State):
    def __init__(self, evt: QtGui.QMouseEvent, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        assert self.grid.numSelected() > 0

        self.click_pos = evt.pos()
        self.delta_pitch = 0
        self.delta_time = audioproc.MusicalDuration(0, 1)

        self.min_time = None  # type: audioproc.MusicalTime
        for interval in self.grid.selection():
            if self.min_time is None or interval.start_time < self.min_time:
                self.min_time = interval.start_time

    def intervals(self) -> Iterator[Tuple[AbstractInterval, bool]]:
        for interval, selected in super().intervals():
            if selected:
                pitch = interval.pitch + self.delta_pitch
                if not 0 <= pitch <= 127:
                    continue
                start_time = interval.start_time + self.delta_time
                end_time = interval.end_time + self.delta_time

                interval = TempInterval(
                    channel=interval.channel,
                    pitch=pitch,
                    velocity=interval.velocity,
                    start_time=start_time,
                    end_time=end_time)
                yield interval, True

            else:
                yield interval, False

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        delta = evt.pos() - self.click_pos
        self.delta_pitch = -int(delta.y() / self.grid.gridYSize())

        min_time = self.min_time + audioproc.MusicalDuration(delta.x() / self.grid.gridXSize())
        if self.grid.shouldSnap(evt):
            min_time = self.grid.snapTime(min_time)
        self.delta_time = min_time - self.min_time

        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            if (self.delta_pitch != 0
                    or self.delta_time != audioproc.MusicalDuration(0, 1)):
                intervals = self.grid.selection()
                self.grid.clearSelection()

                with self.grid.collect_mutations():
                    for interval in intervals:
                        self.grid.removeEvent(interval.start_id)
                        if interval.end_event is not None:
                            self.grid.removeEvent(interval.end_id)

                    segment_start_time = audioproc.MusicalTime(0, 1)
                    segment_end_time = audioproc.MusicalTime(0, 1) + self.grid.duration()

                    for interval in intervals:
                        pitch = interval.pitch + self.delta_pitch
                        if not 0 <= pitch <= 127:
                            continue

                        start_time = interval.start_time + self.delta_time
                        end_time = interval.end_time + self.delta_time
                        if end_time <= segment_start_time:
                            continue
                        if start_time >= segment_end_time:
                            continue

                        start_time = max(segment_start_time, start_time)
                        end_time = min(segment_end_time, end_time)
                        if start_time == end_time:
                            continue

                        interval = self.grid.addInterval(
                            interval.channel, pitch, interval.velocity,
                            start_time, end_time - start_time)

                        self.grid.addToSelection(interval)

            self.grid.resetCurrentState()
            evt.accept()


class PianoRollGrid(slots.SlotContainer, QtWidgets.QWidget):
    playNote = QtCore.pyqtSignal(int)

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
    snapToGrid, setSnapToGrid, snapToGridChanged = slots.slot(bool, 'snapToGrid', default=True)
    hoverPitch, setHoverPitch, hoverPitchChanged = slots.slot(int, 'hoverPitch', default=-1)

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

    # Sadly pylint is confused by the use of __current_state in many methods below.
    # pylint: disable=attribute-defined-outside-init

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.mutations = core.Callback[Sequence[Mutation]]()

        self.__collected_mutations = None  # type: List[Mutation]

        self.__bg_color = QtGui.QColor(245, 245, 245)
        self.__black_key_color = QtGui.QColor(230, 230, 230)
        self.__grid1_color = QtGui.QColor(180, 180, 180)
        self.__grid2_color = QtGui.QColor(195, 195, 195)
        self.__grid3_color = QtGui.QColor(210, 210, 210)
        self.__grid4_color = QtGui.QColor(225, 225, 225)
        self.__grid5_color = QtGui.QColor(240, 240, 240)
        self.__note_color = QtGui.QColor(100, 100, 255)
        self.__add_interval_color = QtGui.QColor(180, 180, 255)
        self.__selected_border1_color = QtGui.QColor(255, 255, 255)
        self.__selected_border2_color = QtGui.QColor(0, 0, 0)
        self.__playback_position_color = QtGui.QColor(0, 0, 0)

        self.__next_event_id = 0
        self.__events = {}  # type: Dict[int, value_types.MidiEvent]
        self.__sorted_events = sortedcontainers.SortedList()

        self.__selection = set()  # type: Set[Interval]

        self.__default_state = DefaultState(grid=self)
        self.__current_state = self.__default_state  # type: State

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

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), self.yOffset())

    def gridWidth(self) -> int:
        return int(self.duration() * self.gridXSize()) + 1

    def gridHeight(self) -> int:
        return 128 * self.gridYSize() + 1

    def gridStep(self) -> audioproc.MusicalDuration:
        for s in (64, 32, 16, 8, 4, 2):
            if self.gridXSize() / s > 24:
                return audioproc.MusicalDuration(1, s)
        return audioproc.MusicalDuration(1, 1)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.gridWidth(), 24 * self.gridYSize())

    def pitchAt(self, y: int) -> int:
        row, offset = divmod(y, self.gridYSize())
        if 0 <= row <= 127:
            return 127 - row
        return -1

    def timeAt(self, x: int) -> audioproc.MusicalTime:
        return audioproc.MusicalTime(x / self.gridXSize())

    def shouldSnap(self, evt: QtGui.QMouseEvent) -> bool:
        return self.snapToGrid() and not evt.modifiers() & Qt.ShiftModifier

    def snapTime(self, time: audioproc.MusicalTime) -> audioproc.MusicalTime:
        grid_time = (
            audioproc.MusicalTime(0, 1)
            + self.gridStep() * int(round(float(time / self.gridStep()))))
        time_x = int(time * self.gridXSize())
        grid_x = int(grid_time * self.gridXSize())
        if abs(time_x - grid_x) <= 10:
            return grid_time
        return time

    def selection(self) -> Set[Interval]:
        return set(self.__selection)

    def numSelected(self) -> int:
        return len(self.__selection)

    def addToSelection(self, interval: Interval) -> None:
        self.__selection.add(interval)
        self.update()

    def removeFromSelection(self, interval: Interval) -> None:
        self.__selection.discard(interval)
        self.update()

    def clearSelection(self) -> None:
        self.__selection.clear()
        self.update()

    def isSelected(self, interval: Interval) -> bool:
        return interval in self.__selection

    def setCurrentState(self, state: State) -> None:
        self.__current_state = state
        self.update()

    def resetCurrentState(self) -> None:
        self.__current_state = self.__default_state
        self.update()

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverPitch(-1)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)
        if evt.size().width() != evt.oldSize().width():
            self.widthChanged.emit(evt.size().width())
        if evt.size().height() != evt.oldSize().height():
            self.heightChanged.emit(evt.size().height())

    def intervals(self, *, channel: int = None, pitch: int = None) -> Iterator[Interval]:
        active_pitches = {}  # type: Dict[Tuple[int, int], Tuple[value_types.MidiEvent, int]]
        for event, event_id in self.__sorted_events:
            if event.midi[0] & 0xf0 not in (0x80, 0x90):
                continue

            ch = event.midi[0] & 0x0f
            if channel is not None and ch != channel:
                continue

            p = event.midi[1]
            if pitch is not None and p != pitch:
                continue

            if (ch, p) in active_pitches:
                start_event, start_event_id = active_pitches.pop((ch, p))
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
                active_pitches[(ch, p)] = (event, event_id)

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

    def intervalAt(self, pitch: int, time: audioproc.MusicalTime) -> Optional[Interval]:
        for interval in self.intervals(pitch=pitch):
            if interval.start_time <= time < interval.end_time:
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
            grid_step = self.gridStep()

            painter.translate(QtCore.QPoint(0, -self.yOffset()))

            y = 0
            for n in reversed(range(0, 128)):
                if n % 12 in {1, 3, 6, 8, 10}:
                    painter.fillRect(0, y, width, grid_y_size, self.__black_key_color)
                y += grid_y_size

            painter.translate(QtCore.QPoint(-self.xOffset(), 0))

            t = audioproc.MusicalTime(0, 1)
            while t <= audioproc.MusicalTime(0, 1) + self.duration():
                x = int(t * grid_x_size)
                if t % audioproc.MusicalTime(1, 4) == audioproc.MusicalTime(0, 1):
                    c = self.__grid1_color
                elif t % audioproc.MusicalTime(1, 8) == audioproc.MusicalTime(0, 1):
                    c = self.__grid2_color
                elif t % audioproc.MusicalTime(1, 16) == audioproc.MusicalTime(0, 1):
                    c = self.__grid3_color
                elif t % audioproc.MusicalTime(1, 32) == audioproc.MusicalTime(0, 1):
                    c = self.__grid4_color
                else:
                    c = self.__grid5_color
                painter.fillRect(x, 0, 1, height, c)
                t += grid_step

            if grid_y_size > 3:
                y = 0
                for n in reversed(range(0, 128)):
                    painter.fillRect(0, y, width, 1, self.__grid1_color)
                    y += grid_y_size
                painter.fillRect(0, y, width, 1, self.__grid1_color)

            for interval, selected in self.__current_state.intervals():
                y = (127 - interval.pitch) * grid_y_size
                x1 = int(interval.start_time * grid_x_size)
                x2 = int(interval.end_time * grid_x_size)
                self.__drawInterval(
                    painter,
                    interval.channel, interval.velocity,
                    selected,
                    x1, x2, y)

            self.__current_state.paintOverlay(painter)

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

        self.__current_state.keyPressEvent(evt)
        if evt.isAccepted():
            return

        super().keyPressEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mousePressEvent(evt)
            return

        self.__current_state.mousePressEvent(evt)
        if evt.isAccepted():
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mouseMoveEvent(evt)
            return

        self.__current_state.mouseMoveEvent(evt)
        if evt.isAccepted():
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.readOnly():
            super().mouseReleaseEvent(evt)
            return

        self.__current_state.mouseReleaseEvent(evt)
        if evt.isAccepted():
            return

        super().mouseReleaseEvent(evt)

    @contextlib.contextmanager
    def collect_mutations(self) -> Generator:
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

        for interval in list(self.intervals(channel=channel, pitch=pitch)):
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
