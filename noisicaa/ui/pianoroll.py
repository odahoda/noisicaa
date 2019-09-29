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
import functools
import fractions
import logging
from typing import (
    Any, Optional, Dict, List, Set, Tuple, Callable, Generator, Iterator, Iterable, Sequence)

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import sortedcontainers

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa import value_types
from . import slots
from . import clipboard
from . import pianoroll_pb2

logger = logging.getLogger(__name__)


class PlayNotes(object):
    def __init__(self) -> None:
        self.note_on = set()  # type: Set[Tuple[int, int]]
        self.note_off = set()  # type: Set[Tuple[int, int]]
        self.all_notes_off = False


class PianoKeys(slots.SlotContainer, QtWidgets.QWidget):
    playNotes = QtCore.pyqtSignal(PlayNotes)

    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)
    playable, setPlayable, playableChanged = slots.slot(bool, 'playable', default=False)
    playbackChannel, setPlaybackChannel, playbackChannelChanged = slots.slot(
        int, 'playbackChannel', default=0)
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
        self.__played_note = None  # type: int
        self.__prev_y = 0
        self.__active_keys = set()  # type: Set[int]

        self.yOffsetChanged.connect(lambda _: self.update())
        self.gridYSizeChanged.connect(lambda _: self.update())

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

                active_keys = self.__active_keys.copy()
                if self.__played_note is not None:
                    active_keys.add(self.__played_note)

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
                        if n in active_keys:
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
                        if n in active_keys:
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
        if (self.playable()
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            pitch = 127 - (evt.pos().y() + self.yOffset()) // self.gridYSize()
            if 0 <= pitch <= 127:
                play_notes = PlayNotes()
                play_notes.note_on.add((self.playbackChannel(), pitch))
                self.playNotes.emit(play_notes)
                self.__played_note = pitch
                self.update()
            evt.accept()
            return

        if (self.scrollable()
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier):
            self.__scrolling = True
            self.__prev_y = evt.pos().y()
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__played_note is not None:
            if 0 <= evt.pos().y() < self.height():
                pitch = 127 - (evt.pos().y() + self.yOffset()) // self.gridYSize()
                if 0 <= pitch <= 127 and pitch != self.__played_note:
                    play_notes = PlayNotes()
                    play_notes.note_off.add((self.playbackChannel(), self.__played_note))
                    play_notes.note_on.add((self.playbackChannel(), pitch))
                    self.playNotes.emit(play_notes)
                    self.__played_note = pitch
                    self.update()
            evt.accept()
            return

        if self.__scrolling:
            dy = evt.pos().y() - self.__prev_y
            self.__prev_y = evt.pos().y()
            self.setYOffset(
                max(0, min(self.gridHeight() - self.height(), self.yOffset() - dy)))
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__played_note is not None:
            play_notes = PlayNotes()
            play_notes.note_off.add((self.playbackChannel(), self.__played_note))
            self.playNotes.emit(play_notes)
            self.__played_note = None
            self.update()
            evt.accept()
            return

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


class EditMode(enum.Enum):
    AddInterval = 1
    SelectRect = 2
    EditVelocity = 3


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


class AbstractInterval(object):  # pragma: no coverage
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

    @property
    def selected(self) -> bool:
        raise NotImplementedError

    @property
    def display_velocity(self) -> bool:
        raise NotImplementedError


class Interval(AbstractInterval):
    __slots__ = ['start_event', 'start_id', 'end_event', 'end_id', '__duration']

    def __init__(
            self, *,
            start_event: value_types.MidiEvent,
            start_id: int,
            end_event: value_types.MidiEvent = None,
            end_id: int = None,
            duration: audioproc.MusicalDuration = None,
            selected: bool = False) -> None:
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
        self.__selected = selected

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

    @property
    def selected(self) -> bool:
        return self.__selected

    @property
    def display_velocity(self) -> bool:
        return False


class TempInterval(AbstractInterval):
    def __init__(
            self, *,
            channel: int, pitch: int, velocity: int,
            start_time: audioproc.MusicalTime, end_time: audioproc.MusicalTime,
            selected: bool,
            display_velocity: bool = False
    ) -> None:
        self.__channel = channel
        self.__pitch = pitch
        self.__velocity = velocity
        self.__start_time = start_time
        self.__end_time = end_time
        self.__selected = selected
        self.__display_velocity = display_velocity

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

    @property
    def selected(self) -> bool:
        return self.__selected

    @property
    def display_velocity(self) -> bool:
        return self.__display_velocity


class State(clipboard.CopyableMixin, QtCore.QObject):
    def __init__(self, *, grid: 'PianoRollGrid') -> None:
        super().__init__()
        self.grid = grid

    def close(self) -> None:
        pass

    def intervals(self) -> Iterator[AbstractInterval]:
        current_channel_intervals = []  # type: List[Interval]
        selected_intervals = []  # type: List[Interval]
        for interval in self.grid.intervals():
            if interval.selected:
                selected_intervals.append(interval)
                continue
            elif interval.channel == self.grid.currentChannel():
                current_channel_intervals.append(interval)
                continue

            yield interval

        yield from current_channel_intervals
        yield from selected_intervals
        yield from self.grid.floatingSelection()

    def paintOverlay(self, painter: QtGui.QPainter) -> None:
        pass

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        pass

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass


class DefaultState(State):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.grid.addAction(self.grid.select_all_action)
        self.grid.addAction(self.grid.select_none_action)
        self.grid.addAction(self.grid.delete_selection_action)
        self.grid.addAction(self.grid.transpose_selection_up_step_action)
        self.grid.addAction(self.grid.transpose_selection_down_step_action)
        self.grid.addAction(self.grid.transpose_selection_up_octave_action)
        self.grid.addAction(self.grid.transpose_selection_down_octave_action)

    def close(self) -> None:
        self.grid.removeAction(self.grid.select_all_action)
        self.grid.removeAction(self.grid.select_none_action)
        self.grid.removeAction(self.grid.transpose_selection_up_step_action)
        self.grid.removeAction(self.grid.transpose_selection_down_step_action)
        self.grid.removeAction(self.grid.transpose_selection_up_octave_action)
        self.grid.removeAction(self.grid.transpose_selection_down_octave_action)

    def copyToClipboard(self) -> music.ClipboardContents:
        data = music.ClipboardContents()
        pianoroll_intervals = data.Extensions[pianoroll_pb2.pianoroll_intervals]

        for interval in self.grid.selection():
            serialized_interval = pianoroll_intervals.intervals.add()
            serialized_interval.time.CopyFrom(interval.start_time.to_proto())
            serialized_interval.duration.CopyFrom(interval.duration.to_proto())
            serialized_interval.channel = interval.channel
            serialized_interval.pitch = interval.pitch
            serialized_interval.velocity = interval.velocity

        return data

    def cutToClipboard(self) -> music.ClipboardContents:
        data = self.copyToClipboard()
        self.grid.deleteSelection()
        return data

    def canPaste(self, data: music.ClipboardContents) -> bool:
        return data.HasExtension(pianoroll_pb2.pianoroll_intervals)

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        assert data.HasExtension(pianoroll_pb2.pianoroll_intervals)
        pianoroll_intervals = data.Extensions[pianoroll_pb2.pianoroll_intervals]

        self.grid.clearSelection()
        for serialized_interval in pianoroll_intervals.intervals:
            time = audioproc.MusicalTime.from_proto(serialized_interval.time)
            duration = audioproc.MusicalDuration.from_proto(serialized_interval.duration)
            interval = TempInterval(
                start_time=time,
                end_time=time + duration,
                channel=serialized_interval.channel,
                pitch=serialized_interval.pitch,
                velocity=serialized_interval.velocity,
                selected=True)
            self.grid.addToFloatingSelection(interval)

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        return False

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        raise AssertionError("This should not happen")

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        # Do not swallow the context menu and let a parent widget show it menu.
        evt.ignore()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pitch = self.grid.pitchAt(evt.pos().y() + self.grid.yOffset())
        time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())

        if evt.button() == Qt.LeftButton:
            floating_selection = self.grid.floatingSelection()
            if floating_selection:
                hit = any(
                    interval.pitch == pitch and interval.start_time <= time <= interval.end_time
                    for interval in floating_selection)

                if hit:
                    self.grid.setCurrentState(MoveSelectionState(
                        grid=self.grid, evt=evt, intervals=floating_selection))
                else:
                    self.grid.clearSelection()
                    with self.grid.collect_mutations():
                        for floating_interval in floating_selection:
                            self.grid.addInterval(
                                channel=floating_interval.channel,
                                pitch=floating_interval.pitch,
                                velocity=floating_interval.velocity,
                                time=floating_interval.start_time,
                                duration=floating_interval.duration)
                evt.accept()
                return

        interval = (
            self.grid.intervalAt(pitch, time, self.grid.currentChannel())
            if pitch >= 0 else None)

        if evt.button() == Qt.LeftButton:
            if interval is not None:
                if not evt.modifiers() & Qt.ControlModifier and not interval.selected:
                    self.grid.clearSelection()

                if evt.modifiers() & Qt.ControlModifier and interval.selected:
                    self.grid.removeFromSelection(interval)
                else:
                    self.grid.addToSelection(interval)

            else:
                if not evt.modifiers() & Qt.ControlModifier:
                    self.grid.clearSelection()

        if (self.grid.editMode() == EditMode.EditVelocity
                and self.grid.numSelected() >= 1
                and evt.button() == Qt.LeftButton):
            self.grid.setCurrentState(ChangeVelocityState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if (self.grid.editMode() == EditMode.AddInterval
                and self.grid.numSelected() <= 1
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            grid_x_size = self.grid.gridXSize()
            for interval in self.grid.intervals(pitch=pitch, channel=self.grid.currentChannel()):
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

        if (self.grid.editMode() == EditMode.SelectRect
                and (interval is None or self.grid.numSelected() == 0)
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.grid.setCurrentState(SelectRectState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if (self.grid.editMode() == EditMode.AddInterval
                and pitch >= 0
                and self.grid.numSelected() == 0
                and evt.button() == Qt.LeftButton
                and evt.modifiers() in (Qt.NoModifier, Qt.ShiftModifier)):
            self.grid.setCurrentState(AddIntervalState(grid=self.grid, evt=evt))
            evt.accept()
            return

        if (self.grid.numSelected() > 0
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.grid.setCurrentState(MoveSelectionState(
                grid=self.grid, evt=evt, intervals=self.grid.selection()))
            evt.accept()
            return

        if pitch >= 0 and evt.button() == Qt.MiddleButton and evt.modifiers() == Qt.NoModifier:
            interval = self.grid.intervalAt(pitch, time, self.grid.currentChannel())
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

        if (self.grid.editMode() == EditMode.AddInterval
                and self.grid.numSelected() <= 1):
            grid_x_size = self.grid.gridXSize()
            for interval in self.grid.intervals(pitch=pitch, channel=self.grid.currentChannel()):
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

        self.channel = self.grid.currentChannel()
        self.pitch = self.grid.pitchAt(evt.pos().y() + self.grid.yOffset())
        self.velocity = self.grid.insertVelocity()
        self.start_time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())
        if self.grid.shouldSnap(evt):
            self.start_time = self.grid.snapTime(self.start_time)
        self.end_time = self.start_time

        self.__played = False

    def intervals(self) -> Iterator[AbstractInterval]:
        yield from super().intervals()

        start_time = self.start_time
        end_time = self.end_time
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        if start_time != end_time:
            interval = TempInterval(
                channel=self.channel,
                pitch=self.pitch,
                velocity=self.velocity,
                start_time=start_time,
                end_time=end_time,
                selected=True)
            yield interval

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.end_time = self.grid.timeAt(evt.pos().x() + self.grid.xOffset())
        if self.grid.shouldSnap(evt):
            self.end_time = self.grid.snapTime(self.end_time)

        if self.end_time != self.start_time and not self.__played:
            play_notes = PlayNotes()
            play_notes.note_on.add((self.channel, self.pitch))
            self.grid.playNotes.emit(play_notes)
            self.__played = True

        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.RightButton:
            self.grid.resetCurrentState()
            evt.accept()
            return

        if evt.button() == Qt.LeftButton:
            start_time = self.start_time
            end_time = self.end_time
            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if start_time != end_time:
                with self.grid.collect_mutations():
                    interval = self.grid.addInterval(
                        self.channel, self.pitch, self.velocity,
                        start_time, end_time - start_time)
                self.grid.clearSelection()
                self.grid.addToSelection(interval)

            play_notes = PlayNotes()
            play_notes.note_off.add((self.channel, self.pitch))
            self.grid.playNotes.emit(play_notes)

            self.grid.resetCurrentState()
            evt.accept()


class SelectRectState(State):
    def __init__(self, evt: QtGui.QMouseEvent, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.channel = self.grid.currentChannel()
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
        for interval in self.grid.intervals(channel=self.channel):
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

    def intervals(self) -> Iterator[AbstractInterval]:
        for interval in super().intervals():
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
                    end_time=end_time,
                    selected=interval.selected)
                yield interval

            else:
                yield interval

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
        if evt.button() == Qt.RightButton:
            self.grid.resetCurrentState()
            evt.accept()
            return

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
    def __init__(
            self, evt: QtGui.QMouseEvent, intervals: Iterable[AbstractInterval], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__intervals = set(intervals)
        assert len(self.__intervals) > 0
        self.click_pos = evt.pos()
        self.delta_pitch = 0
        self.delta_time = audioproc.MusicalDuration(0, 1)

        self.min_time = min(
            interval.start_time for interval in self.__intervals)

    def intervals(self) -> Iterator[AbstractInterval]:
        for interval in super().intervals():
            if interval in self.__intervals:
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
                    end_time=end_time,
                    selected=interval.selected)
                yield interval

            else:
                yield interval

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        delta = evt.pos() - self.click_pos

        delta_pitch = -int(delta.y() / self.grid.gridYSize())
        if delta_pitch != self.delta_pitch:
            play_notes = PlayNotes()
            play_notes.all_notes_off = True
            for interval in self.grid.selection():
                pitch = interval.pitch + delta_pitch
                if 0 <= pitch <= 127:
                    play_notes.note_on.add((interval.channel, pitch))
            if play_notes.note_on:
                self.grid.playNotes.emit(play_notes)
            self.delta_pitch = delta_pitch

        min_time = self.min_time + audioproc.MusicalDuration(delta.x() / self.grid.gridXSize())
        if self.grid.shouldSnap(evt):
            min_time = self.grid.snapTime(min_time)
        self.delta_time = min_time - self.min_time

        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.RightButton:
            self.grid.resetCurrentState()
            evt.accept()
            return

        if evt.button() == Qt.LeftButton:
            play_notes = PlayNotes()
            play_notes.all_notes_off = True
            self.grid.playNotes.emit(play_notes)

            if (self.delta_pitch != 0
                    or self.delta_time != audioproc.MusicalDuration(0, 1)):
                self.grid.clearSelection()

                with self.grid.collect_mutations():
                    for interval in self.__intervals:
                        if not isinstance(interval, Interval):
                            continue
                        self.grid.removeEvent(interval.start_id)
                        if interval.end_event is not None:
                            self.grid.removeEvent(interval.end_id)

                    segment_start_time = audioproc.MusicalTime(0, 1)
                    segment_end_time = audioproc.MusicalTime(0, 1) + self.grid.duration()

                    for interval in self.__intervals:
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


class ChangeVelocityState(State):
    def __init__(self, evt: QtGui.QMouseEvent, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        assert self.grid.numSelected() > 0

        self.prev_pos = evt.pos()
        self.delta_velocity = 0.0

    def intervals(self) -> Iterator[AbstractInterval]:
        delta_velocity = int(self.delta_velocity)
        for interval in super().intervals():
            if interval.selected:
                velocity = max(1, min(127, interval.velocity + delta_velocity))

                interval = TempInterval(
                    channel=interval.channel,
                    pitch=interval.pitch,
                    velocity=velocity,
                    start_time=interval.start_time,
                    end_time=interval.end_time,
                    selected=True,
                    display_velocity=True)
                yield interval

            else:
                yield interval

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        delta_x = evt.pos().x() - self.prev_pos.x()
        self.prev_pos = evt.pos()

        if evt.modifiers() == Qt.ShiftModifier:
            delta = delta_x / 10
        else:
            delta = delta_x / 3

        self.delta_velocity += delta
        self.grid.update()
        evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.RightButton:
            self.grid.resetCurrentState()
            evt.accept()
            return

        if evt.button() == Qt.LeftButton:
            delta_velocity = int(self.delta_velocity)
            if delta_velocity != 0:
                intervals = self.grid.selection()
                self.grid.clearSelection()

                with self.grid.collect_mutations():
                    for interval in intervals:
                        self.grid.removeEvent(interval.start_id)

                        velocity = max(1, min(127, interval.velocity + delta_velocity))
                        start_event = value_types.MidiEvent(
                            interval.start_time,
                            bytes([0x90 | interval.channel, interval.pitch, velocity]))
                        start_id = self.grid.addEvent(start_event)

                        if interval.end_event is not None:
                            new_interval = Interval(
                                start_event=start_event,
                                start_id=start_id,
                                end_event=interval.end_event,
                                end_id=interval.end_id)
                        else:
                            new_interval = Interval(
                                start_event=start_event,
                                start_id=start_id,
                                duration=interval.duration)
                        self.grid.addToSelection(new_interval)

            self.grid.resetCurrentState()
            evt.accept()


class PianoRollGrid(clipboard.CopyableMixin, slots.SlotContainer, QtWidgets.QWidget):
    playNotes = QtCore.pyqtSignal(PlayNotes)

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
    editMode, setEditMode, editModeChanged = slots.slot(
        EditMode, 'editMode', default=EditMode.AddInterval)
    currentChannel, setCurrentChannel, currentChannelChanged = slots.slot(
        int, 'currentChannel', default=0)
    overlayColor, setOverlayColor, overlayColorChanged = slots.slot(
        QtGui.QColor, 'overlayColor', default=QtGui.QColor(0, 0, 0, 0))
    insertVelocity, setInsertVelocity, insertVelocityChanged = slots.slot(
        int, 'insertVelocity', default=100)

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

        self.__selection = set()  # type: Set[int]
        self.__floating_selection = set()  # type: Set[AbstractInterval]

        self.__current_state = None  # type: State

        self.__readOnlyChanged(self.readOnly())
        self.readOnlyChanged.connect(self.__readOnlyChanged)

        self.playbackPositionChanged.connect(lambda _: self.update())
        self.durationChanged.connect(lambda _: self.update())
        self.unfinishedNoteModeChanged.connect(lambda _: self.update())
        self.xOffsetChanged.connect(lambda _: self.update())
        self.yOffsetChanged.connect(lambda _: self.update())
        self.currentChannelChanged.connect(lambda _: self.update())
        self.overlayColorChanged.connect(lambda _: self.update())

        self.durationChanged.connect(lambda _: self.gridWidthChanged.emit(self.gridWidth()))

        def createAction(seq: str, func: Callable[[], None]) -> QtWidgets.QAction:
            action = QtWidgets.QAction(self)
            action.setEnabled(not self.readOnly())
            self.readOnlyChanged.connect(lambda _: action.setEnabled(not self.readOnly()))
            action.setShortcut(QtGui.QKeySequence(seq))
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.triggered.connect(func)
            return action

        self.select_all_action = createAction('ctrl+a', self.__selectAll)
        self.select_none_action = createAction('ctrl+shift+a', self.__selectNone)
        self.delete_selection_action = createAction('del', self.deleteSelection)
        self.transpose_selection_up_step_action = createAction(
            'up', functools.partial(self.__transposeSelection, 1))
        self.transpose_selection_down_step_action = createAction(
            'down', functools.partial(self.__transposeSelection, -1))
        self.transpose_selection_up_octave_action = createAction(
            'shift+up', functools.partial(self.__transposeSelection, 12))
        self.transpose_selection_down_octave_action = createAction(
            'shift+down', functools.partial(self.__transposeSelection, -12))

        self.resetCurrentState()

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
        row = y // self.gridYSize()
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
        intervals = set()  # type: Set[Interval]
        for interval in self.intervals():
            if interval.start_id in self.__selection:
                intervals.add(interval)
        return intervals

    def numSelected(self) -> int:
        return len(self.__selection)

    def __selectionChanged(self) -> None:
        self.setCanCopy(bool(self.__selection))
        self.setCanCut(bool(self.__selection))
        self.update()

    def addToSelection(self, interval: Interval) -> None:
        self.__selection.add(interval.start_id)
        self.__selectionChanged()

    def removeFromSelection(self, interval: Interval) -> None:
        self.__selection.discard(interval.start_id)
        self.__selectionChanged()

    def clearSelection(self) -> None:
        self.__selection.clear()
        self.__floating_selection.clear()
        self.__selectionChanged()

    def floatingSelection(self) -> Set[AbstractInterval]:
        return set(self.__floating_selection)

    def addToFloatingSelection(self, interval: AbstractInterval) -> None:
        self.__floating_selection.add(interval)
        self.__selectionChanged()

    def copyToClipboard(self) -> music.ClipboardContents:
        return self.__current_state.copyToClipboard()

    def cutToClipboard(self) -> music.ClipboardContents:
        return self.__current_state.cutToClipboard()

    def canPaste(self, data: music.ClipboardContents) -> bool:
        return self.__current_state.canPaste(data)

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        self.__current_state.pasteFromClipboard(data)

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        return self.__current_state.canPasteAsLink(data)

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        self.__current_state.pasteAsLinkFromClipboard(data)

    def setCurrentState(self, state: State) -> None:
        if self.__current_state is not None:
            self.__current_state.close()
        self.__current_state = state
        self.update()

    def resetCurrentState(self) -> None:
        self.setCurrentState(DefaultState(grid=self))

    def __selectAll(self) -> None:
        for interval in self.intervals(channel=self.currentChannel()):
            self.addToSelection(interval)

    def __selectNone(self) -> None:
        self.clearSelection()

    def deleteSelection(self) -> None:
        if self.numSelected() > 0:
            intervals = self.selection()
            self.clearSelection()

            with self.collect_mutations():
                for interval in intervals:
                    self.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.removeEvent(interval.end_id)

    def __transposeSelection(self, delta: int) -> None:
        if self.numSelected() > 0:
            intervals = self.selection()
            self.clearSelection()

            with self.collect_mutations():
                for interval in intervals:
                    self.removeEvent(interval.start_id)
                    if interval.end_event is not None:
                        self.removeEvent(interval.end_id)

                for interval in intervals:
                    pitch = interval.pitch + delta
                    if not 0 <= pitch <= 127:
                        continue

                    interval = self.addInterval(
                        interval.channel, pitch, interval.velocity,
                        interval.start_time, interval.duration)

                    self.addToSelection(interval)

    def __readOnlyChanged(self, readonly: bool) -> None:
        if readonly:
            self.clearFocus()
            self.setFocusPolicy(Qt.NoFocus)
            self.setMouseTracking(False)
        else:
            self.setFocusPolicy(Qt.StrongFocus)
            self.setMouseTracking(True)
        self.update()

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverPitch(-1)

    def focusInEvent(self, evt: QtGui.QFocusEvent) -> None:
        super().focusInEvent(evt)
        self.update()

    def focusOutEvent(self, evt: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(evt)
        self.update()

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
                        end_event=event,
                        selected=start_event_id in self.__selection)
                else:
                    yield Interval(
                        start_id=start_event_id,
                        start_event=start_event,
                        duration=event.time - start_event.time,
                        selected=start_event_id in self.__selection)

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
                    duration=end_time - event.time,
                    selected=event_id in self.__selection)

    def intervalAt(
            self,
            pitch: int,
            time: audioproc.MusicalTime,
            channel: int = None
    ) -> Optional[Interval]:
        for interval in self.intervals(pitch=pitch, channel=channel):
            if interval.start_time <= time < interval.end_time:
                return interval

        return None

    def pointAt(
            self,
            pitch: int,
            time: audioproc.MusicalTime,
    ) -> QtCore.QPoint:
        assert 0 <= pitch <= 127
        assert audioproc.MusicalTime(0, 1) <= time <= self.duration().as_time()
        x = int(time * self.gridXSize())
        y = (127 - pitch) * self.gridYSize() + self.gridYSize() // 2
        return QtCore.QPoint(x, y) - self.offset()

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

            painter.translate(0, -self.yOffset())

            y = 0
            for n in reversed(range(0, 128)):
                if n % 12 in {1, 3, 6, 8, 10}:
                    painter.fillRect(0, y, width, grid_y_size, self.__black_key_color)
                y += grid_y_size

            painter.translate(-self.xOffset(), 0)

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

            other_channels_pixmap = QtGui.QPixmap(self.size())
            other_channels_pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            other_channels_painter = QtGui.QPainter(other_channels_pixmap)
            other_channels_painter.translate(-self.xOffset(), -self.yOffset())
            current_channel_pixmap = QtGui.QPixmap(self.size())
            current_channel_pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            current_channel_painter = QtGui.QPainter(current_channel_pixmap)
            current_channel_painter.translate(-self.xOffset(), -self.yOffset())

            try:
                for interval in self.__current_state.intervals():
                    y = (127 - interval.pitch) * grid_y_size
                    x1 = int(interval.start_time * grid_x_size)
                    x2 = int(interval.end_time * grid_x_size)

                    if interval.selected or interval.channel == self.currentChannel():
                        interval_painter = current_channel_painter
                    else:
                        interval_painter = other_channels_painter

                    self.__drawInterval(
                        interval_painter,
                        interval.channel, interval.velocity,
                        interval.selected and not self.readOnly(),
                        x1, x2, y)

            finally:
                other_channels_painter.end()
                current_channel_painter.end()

            painter.save()
            painter.setOpacity(0.2)
            painter.drawPixmap(self.xOffset(), self.yOffset(), other_channels_pixmap)
            painter.restore()
            painter.drawPixmap(self.xOffset(), self.yOffset(), current_channel_pixmap)

            font = QtGui.QFont(self.font())
            font.setPixelSize(max(10, min(20, grid_y_size - 2)))
            font_metrics = QtGui.QFontMetrics(font)
            painter.setFont(font)
            painter.setPen(Qt.black)

            label_rect = font_metrics.boundingRect('127').adjusted(-3, 0, 3, 0)

            for interval in self.__current_state.intervals():
                if not interval.display_velocity:
                    continue

                y = (127 - interval.pitch) * grid_y_size - label_rect.bottom()
                x = int(interval.start_time * grid_x_size) - label_rect.left()
                r = label_rect.translated(x, y)
                painter.fillRect(r, QtGui.QColor(200, 200, 160))
                painter.fillRect(r.adjusted(1, 1, -1, -1), QtGui.QColor(255, 255, 200))
                painter.drawText(r.adjusted(3, 0, -3, 0), Qt.AlignRight, '%d' % interval.velocity)

            self.__current_state.paintOverlay(painter)

            overlay_color = self.overlayColor()
            if overlay_color.alpha() > 0:
                s_color = QtGui.QColor(255, 255, 255)
                tl_color = QtGui.QColor.fromHsvF(
                    overlay_color.hueF(),
                    0.3 * overlay_color.saturationF(),
                    0.5 + 0.5 * overlay_color.valueF())
                br_color = QtGui.QColor.fromHsvF(
                    overlay_color.hueF(),
                    0.3 * overlay_color.saturationF(),
                    0.5 * overlay_color.valueF())
                w = self.width()
                h = self.height()

                painter.translate(self.xOffset(), self.yOffset())
                painter.fillRect(0, 0, 7, 1, s_color)
                painter.fillRect(0, 1, 1, 6, s_color)
                painter.fillRect(7, 0, w - 7, 1, tl_color)
                painter.fillRect(0, 7, 1, h - 7, tl_color)
                painter.fillRect(1, h - 1, w - 1, 1, br_color)
                painter.fillRect(w - 1, 1, 1, h - 2, br_color)
                painter.fillRect(1, 1, 3, 1, s_color)
                painter.fillRect(1, 2, 1, 2, s_color)
                painter.fillRect(4, 1, w - 5, 1, tl_color)
                painter.fillRect(1, 4, 1, h - 5, tl_color)
                painter.fillRect(2, h - 2, w - 3, 1, br_color)
                painter.fillRect(w - 2, 2, 1, h - 4, br_color)
                painter.fillRect(2, 2, w - 4, h - 4, overlay_color)
                painter.translate(-self.xOffset(), -self.yOffset())

            if not self.readOnly() and self.hasFocus():
                f_color = QtGui.QColor(0, 0, 0)
                painter.translate(self.xOffset(), self.yOffset())
                painter.fillRect(0, 0, self.width(), 1, f_color)
                painter.fillRect(0, 1, 1, self.height() - 2, f_color)
                painter.fillRect(self.width() - 1, 1, 1, self.height() - 2, f_color)
                painter.fillRect(0, self.height() - 1, self.width(), 1, f_color)
                painter.translate(-self.xOffset(), -self.yOffset())

            playback_position = self.playbackPosition()
            if playback_position.numerator >= 0:
                x = int(playback_position * grid_x_size)
                painter.fillRect(x, 0, 1, height, self.__playback_position_color)

        finally:
            painter.end()

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        if self.readOnly():
            super().contextMenuEvent(evt)
            return

        self.__current_state.contextMenuEvent(evt)
        if evt.isAccepted():
            return

        super().contextMenuEvent(evt)

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

    def events(self) -> List[value_types.MidiEvent]:
        return [event for event, _ in self.__sorted_events]

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
        self.__grid.setMinimumSize(100, 50)
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
