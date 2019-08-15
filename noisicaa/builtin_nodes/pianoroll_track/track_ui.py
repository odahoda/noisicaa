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
from typing import Any, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtSvg

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa import value_types
from noisicaa.ui import svg_symbol
from noisicaa.ui.track_list import tools
from noisicaa.ui.track_list import base_track_editor
from noisicaa.ui.track_list import time_view_mixin
from . import model

logger = logging.getLogger(__name__)


class EditSegmentsTool(tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.EDIT_PIANOROLL_SEGMENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'edit-pianoroll-segments'

    def mousePressEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, PianoRollTrackEditor), type(target).__name__

        super().mousePressEvent(target, evt)

    def mouseMoveEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, PianoRollTrackEditor), type(target).__name__

        super().mouseMoveEvent(target, evt)

    def mouseReleaseEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, PianoRollTrackEditor), type(target).__name__

        super().mouseReleaseEvent(target, evt)

    def mouseDoubleClickEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, PianoRollTrackEditor), type(target).__name__

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            time = target.xToTime(evt.pos().x())
            for segment_ref in target.track.segments:
                if segment_ref.time <= time <= segment_ref.time + segment_ref.segment.duration:
                    # double clicked on a segment
                    # TODO: switch to midi editor tool
                    break
            else:
                with self.project.apply_mutations('%s: Insert segment' % target.track.name):
                    target.track.create_segment(
                        time, audioproc.MusicalDuration(4, 4))

            evt.accept()
            return

        super().mouseDoubleClickEvent(target, evt)


class PianoRollToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(EditSegmentsTool(context=self.context))


class SegmentEditor(core.AutoCleanupMixin, object):
    def __init__(self, track_editor: 'PianoRollTrackEditor', segment_ref: model.PianoRollSegmentRef) -> None:
        super().__init__()

        self.__track_editor = track_editor
        self.__segment_ref = segment_ref
        self.__segment = segment_ref.segment

    def startTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time

    def endTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time + self.__segment.duration

    def duration(self) -> audioproc.MusicalDuration:
        return self.__segment.duration

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        width = self.__track_editor.timeToX(self.endTime()) - self.__track_editor.timeToX(self.startTime())
        height = self.__track_editor.height()

        painter.fillRect(0, 0, width, height, QtGui.QColor(160, 160, 255))
        painter.fillRect(-2, 0, 2, height, Qt.black)
        painter.fillRect(width, 0, 2, height, Qt.black)

        painter.drawText(2, 10, str(self.__segment_ref.id))


class PianoRollTrackEditor(time_view_mixin.ContinuousTimeMixin, base_track_editor.BaseTrackEditor):
    toolBoxClass = PianoRollToolBox

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = core.ListenerList()
        self.segments = []  # type: List[SegmentEditor]

        for segment_ref in self.track.segments:
            self.__addSegment(len(self.segments), segment_ref)
        self.__listeners.add(self.track.segments_changed.add(self.__segmentsChanged))

        self.setHeight(240)

    def __addSegment(self, insert_index: int, segment_ref: model.PianoRollSegmentRef) -> None:
        seditor = SegmentEditor(track_editor=self, segment_ref=segment_ref)
        self.segments.insert(insert_index, seditor)
        self.rectChanged.emit(self.viewRect())

    def __removeSegment(self, remove_index: int, point: QtCore.QPoint) -> None:
        seditor = self.segments.pop(remove_index)
        seditor.cleanup()
        self.rectChanged.emit(self.viewRect())

    def __segmentsChanged(self, change: music.PropertyListChange[model.PianoRollSegmentRef]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addSegment(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeSegment(change.index, change.old_value)

        else:
            raise TypeError(type(change))

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        super().paint(painter, paint_rect)

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

        for segment in self.segments:
            x1 = self.timeToX(segment.startTime())
            x2 = self.timeToX(segment.endTime())
            segment_rect = QtCore.QRect(x1, 0, x2 - x1, self.height())
            segment_rect = segment_rect.adjusted(-2, 0, 2, 0)
            segment_rect = segment_rect.intersected(paint_rect)
            logger.error(segment_rect)
            if not segment_rect.isEmpty():
                painter.save()
                try:
                    painter.translate(x1, 0)
                    segment.paint(painter, segment_rect.translated(-x1, 0))
                finally:
                    painter.restore()
