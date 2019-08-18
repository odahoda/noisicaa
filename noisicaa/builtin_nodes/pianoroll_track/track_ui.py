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
from typing import Any, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui import pianoroll
from noisicaa.ui import slots
from noisicaa.ui.track_list import tools
from noisicaa.ui.track_list import base_track_editor
from noisicaa.ui.track_list import time_view_mixin
from . import model

logger = logging.getLogger(__name__)


class ArrangeSegmentsTool(tools.ToolBase):
    track = None  # type: PianoRollTrackEditor

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.ARRANGE_PIANOROLL_SEGMENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

        self.__action = None  # type: str

        self.__segment = None  # type: SegmentEditor
        self.__handle_offset = None  # type: int

    def iconName(self) -> str:
        return 'arrange-pianoroll-segments'

    def __segmentAt(self, x: int) -> 'SegmentEditor':
        for seditor in self.track.segments:
            if seditor.trackX() <= x < seditor.trackX() + seditor.width():
                return seditor
        return None

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            for seditor in self.track.segments:
                x1 = seditor.trackX()
                x2 = seditor.trackX() + seditor.width()

                if abs(x2 - evt.pos().x()) < 4:
                    self.__action = 'move-end'
                    self.__segment = seditor
                    self.__handle_offset = evt.pos().x() - x2
                    evt.accept()
                    return

                if abs(x1 - evt.pos().x()) < 4:
                    self.__action = 'move-start'
                    self.__segment = seditor
                    self.__handle_offset = evt.pos().x() - x1
                    evt.accept()
                    return

                if x1 <= evt.pos().x() < x2:
                    self.__action = 'drag'
                    self.__segment = seditor
                    self.__handle_offset = evt.pos().x() - x1
                    evt.accept()
                    return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__action == 'drag':
            self.__segment.move(max(self.track.timeToX(audioproc.MusicalTime(0, 1)), evt.pos().x() - self.__handle_offset) - self.track.xOffset(), 0)
            evt.accept()
            return

        if self.__action == 'move-end':
            self.__segment.resize(max(5, evt.pos().x() - self.__segment.trackX() - self.__handle_offset), self.track.height())
            evt.accept()
            return

        if self.__action == 'move-start':
            x2 = self.__segment.trackX() + self.__segment.width()
            x1 = max(self.track.timeToX(audioproc.MusicalTime(0, 1)), min(x2 - 5, evt.pos().x() - self.__handle_offset))
            self.__segment.move(x1 - self.track.xOffset(), 0)
            self.__segment.resize(x2 - x1, self.track.height())
            evt.accept()
            return

        for seditor in self.track.segments:
            x1 = seditor.trackX()
            x2 = seditor.trackX() + seditor.width()

            if abs(x2 - evt.pos().x()) < 4:
                self.track.setCursor(Qt.SizeHorCursor)
                break
            elif abs(x1 - evt.pos().x()) < 4:
                self.track.setCursor(Qt.SizeHorCursor)
                break
            elif x1 <= evt.pos().x() < x2:
                self.track.setCursor(Qt.DragMoveCursor)
                break
        else:
            self.track.unsetCursor()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__action == 'drag':
            with self.project.apply_mutations('%s: Move segment' % self.track.track.name):
                self.__segment.segmentRef().time = self.track.xToTime(self.__segment.trackX())
            self.__segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'move-start':
            with self.project.apply_mutations('%s: Resize segment' % self.track.track.name):
                self.__segment.segmentRef().time = self.track.xToTime(self.__segment.trackX())
                self.__segment.segment().duration = audioproc.MusicalDuration((self.__segment.width() - 1) / self.track.scaleX())
            self.__segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'move-end':
            with self.project.apply_mutations('%s: Resize segment' % self.track.track.name):
                self.__segment.segment().duration = audioproc.MusicalDuration((self.__segment.width() - 1) / self.track.scaleX())
            self.__segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__action in ('drag', 'move-start', 'move-end'):
            self.__segment.move(self.track.timeToX(self.__segment.startTime()) - self.track.xOffset(), 0)
            self.__segment.resize(int(self.track.scaleX() * self.__segment.duration().fraction) + 1, self.track.height())
            self.__segment = None
            self.__action = None
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            seditor = self.__segmentAt(evt.pos().x())
            if seditor is not None:
                # TODO: switch to midi editor tool
                with self.project.apply_mutations('%s: Remove segment' % self.track.track.name):
                    self.track.track.remove_segment(seditor.segmentRef())

            else:
                time = self.track.xToTime(evt.pos().x())
                with self.project.apply_mutations('%s: Insert segment' % self.track.track.name):
                    self.track.track.create_segment(
                        time, audioproc.MusicalDuration(4, 4))

            evt.accept()
            return

        super().mouseDoubleClickEvent(evt)


class EditEventsTool(tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.EDIT_PIANOROLL_EVENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'edit-pianoroll-events'


class PianoRollToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(ArrangeSegmentsTool)
        self.addTool(EditEventsTool)


class SegmentEditor(slots.SlotContainer, core.AutoCleanupMixin, QtWidgets.QWidget):
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    scaleX, setScaleX, scaleXChanged = slots.slot(fractions.Fraction, 'scaleX', default=fractions.Fraction(4*80))
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)

    def __init__(self, track_editor: 'PianoRollTrackEditor', segment_ref: model.PianoRollSegmentRef) -> None:
        super().__init__(parent=track_editor)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__track_editor = track_editor
        self.__segment_ref = segment_ref
        self.__segment = segment_ref.segment

        self.__listeners.add(self.__segment_ref.time_changed.add(self.__timeChanged))
        self.__listeners.add(self.__segment.duration_changed.add(self.__durationChanged))

        self.__grid = pianoroll.PianoRollGrid(parent=self)
        self.__grid.move(0, -self.yOffset())
        self.__grid.setGridXSize(self.scaleX())
        self.__grid.setDuration(self.__segment.duration)

        self.scaleXChanged.connect(self.__grid.setGridXSize)
        self.gridYSizeChanged.connect(self.__grid.setGridYSize)
        self.yOffsetChanged.connect(lambda _: self.__grid.move(0, -self.yOffset()))

    def __timeChanged(self, change: music.PropertyValueChange[audioproc.MusicalTime]) -> None:
        self.move(self.__track_editor.timeToX(change.new_value) - self.__track_editor.xOffset(), 0)

    def __durationChanged(self, change: music.PropertyValueChange[audioproc.MusicalDuration]) -> None:
        self.__grid.setDuration(change.new_value)
        self.resize(int(self.__track_editor.scaleX() * change.new_value.fraction) + 1, self.__track_editor.height())

    def trackX(self) -> int:
        return self.x() + self.__track_editor.xOffset()

    def segmentRef(self) -> model.PianoRollSegmentRef:
        return self.__segment_ref

    def segment(self) -> model.PianoRollSegment:
        return self.__segment

    def startTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time

    def endTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time + self.__segment.duration

    def duration(self) -> audioproc.MusicalDuration:
        return self.__segment.duration

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        self.__grid.resize(self.width(), self.__grid.gridHeight())
        self.__grid.setDuration(audioproc.MusicalDuration((self.width() - 1) / self.__track_editor.scaleX()))
        super().resizeEvent(evt)


class PianoRollTrackEditor(slots.SlotContainer, time_view_mixin.ContinuousTimeMixin, base_track_editor.BaseTrackEditor):
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)

    def __init__(self, **kwargs: Any) -> None:
        self.segments = []  # type: List[SegmentEditor]

        super().__init__(**kwargs)

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__keys = pianoroll.PianoKeys(parent=self)
        self.__keys.setYOffset(self.yOffset())
        self.yOffsetChanged.connect(self.__keys.setYOffset)
        self.__keys.setGridYSize(self.gridYSize())
        self.gridYSizeChanged.connect(self.__keys.setGridYSize)

        self.__y_scrollbar = QtWidgets.QScrollBar(orientation=Qt.Vertical, parent=self)
        self.__y_scrollbar.setFixedWidth(16)
        self.__y_scrollbar.setRange(0, 500)
        self.__y_scrollbar.setSingleStep(20)
        self.__y_scrollbar.setPageStep(self.height())
        self.__y_scrollbar.setValue(self.yOffset())

        self.__y_scrollbar.valueChanged.connect(self.setYOffset)

        for segment_ref in self.track.segments:
            self.__addSegment(len(self.segments), segment_ref)
        self.__listeners.add(self.track.segments_changed.add(self.__segmentsChanged))

        self.setAutoScroll(False)
        self.setFixedHeight(240)

        self.xOffsetChanged.connect(lambda _: self.__repositionSegments())
        self.xOffsetChanged.connect(lambda _: self.update())
        self.scaleXChanged.connect(lambda _: self.__resizeSegments())
        self.gridYSizeChanged.connect(lambda _: self.__updateYScrollbar())

    @property
    def track(self) -> model.PianoRollTrack:
        return down_cast(model.PianoRollTrack, super().track)

    def createToolBox(self) -> PianoRollToolBox:
        return PianoRollToolBox(track=self, context=self.context)

    def __addSegment(self, insert_index: int, segment_ref: model.PianoRollSegmentRef) -> None:
        seditor = SegmentEditor(track_editor=self, segment_ref=segment_ref)
        self.segments.insert(insert_index, seditor)
        seditor.setEnabled(self.isCurrent())
        seditor.resize(int(self.scaleX() * segment_ref.segment.duration.fraction) + 1, self.height())
        seditor.move(self.timeToX(segment_ref.time) - self.xOffset(), 0)
        seditor.setScaleX(self.scaleX())
        seditor.setYOffset(self.yOffset())
        self.yOffsetChanged.connect(seditor.setYOffset)
        seditor.show()

        self.__keys.raise_()
        self.__y_scrollbar.raise_()

        self.update()

    def __removeSegment(self, remove_index: int, point: QtCore.QPoint) -> None:
        seditor = self.segments.pop(remove_index)
        seditor.cleanup()
        seditor.hide()
        seditor.setParent(None)
        self.update()

    def __segmentsChanged(self, change: music.PropertyListChange[model.PianoRollSegmentRef]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addSegment(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeSegment(change.index, change.old_value)

        else:
            raise TypeError(type(change))

    def setIsCurrent(self, is_current: bool) -> None:
        super().setIsCurrent(is_current)
        for segment in self.segments:
            segment.setEnabled(is_current)

    def __repositionSegments(self) -> None:
        for segment in self.segments:
            segment.move(self.timeToX(segment.startTime()) - self.xOffset(), 0)

    def __resizeSegments(self) -> None:
        for seditor in self.segments:
            seditor.resize(int(self.scaleX() * seditor.duration().fraction) + 1, self.height())
            seditor.move(self.timeToX(seditor.startTime()) - self.xOffset(), 0)
            seditor.setScaleX(self.scaleX())

    def __updateYScrollbar(self) -> None:
        grid_height = 128 * self.gridYSize() + 1
        self.__y_scrollbar.setRange(0, max(0, grid_height - self.height()))
        self.__y_scrollbar.setPageStep(self.height())

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.__keys.move(0, 0)
        self.__keys.resize(self.__keys.width(), self.height())

        self.__y_scrollbar.move(self.width() - self.__y_scrollbar.width(), 0)
        self.__y_scrollbar.resize(self.__y_scrollbar.width(), self.height())

        self.__updateYScrollbar()

        for segment in self.segments:
            segment.resize(segment.width(), self.height())

    def _paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        painter.setPen(Qt.black)

        beat_time = audioproc.MusicalTime()
        beat_num = 0
        while beat_time < self.projectEndTime():
            x = self.timeToX(beat_time)

            if beat_num == 0:
                painter.fillRect(x, 0, 2, self.height(), Qt.black)
            else:
                painter.fillRect(x, 0, 1, self.height(), QtGui.QColor(160, 160, 160))

            beat_time += audioproc.MusicalDuration(1, 4)
            beat_num += 1

        x = self.timeToX(self.projectEndTime())
        painter.fillRect(x, 0, 2, self.height(), Qt.black)
