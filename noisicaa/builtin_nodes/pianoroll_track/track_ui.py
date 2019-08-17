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
from typing import Any, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
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

        logger.error(evt.pos())
        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            time = target.xToTime(evt.pos().x())
            for segment_ref in target.track.segments:
                if segment_ref.time <= time <= segment_ref.time + segment_ref.segment.duration:
                    # TODO: switch to midi editor tool
                    with self.project.apply_mutations('%s: Remove segment' % target.track.name):
                        target.track.remove_segment(segment_ref)
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


class SegmentEditor(core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, track_editor: 'PianoRollTrackEditor', segment_ref: model.PianoRollSegmentRef) -> None:
        super().__init__(parent=track_editor)

        self.__track_editor = track_editor
        self.__segment_ref = segment_ref
        self.__segment = segment_ref.segment

        l = QtWidgets.QVBoxLayout()
        l.addWidget(QtWidgets.QLabel("hello"))
        l.addWidget(QtWidgets.QLineEdit())
        self.setLayout(l)

    def startTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time

    def endTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time + self.__segment.duration

    def duration(self) -> audioproc.MusicalDuration:
        return self.__segment.duration


class PianoRollTrackEditor(time_view_mixin.ContinuousTimeMixin, base_track_editor.BaseTrackEditor):
    toolBoxClass = PianoRollToolBox

    def __init__(self, **kwargs: Any) -> None:
        self.__listeners = core.ListenerList()
        self.segments = []  # type: List[SegmentEditor]

        super().__init__(**kwargs)

        for segment_ref in self.track.segments:
            self.__addSegment(len(self.segments), segment_ref)
        self.__listeners.add(self.track.segments_changed.add(self.__segmentsChanged))

        self.setFixedHeight(240)

    @property
    def track(self) -> model.PianoRollTrack:
        return down_cast(model.PianoRollTrack, super().track)

    def __addSegment(self, insert_index: int, segment_ref: model.PianoRollSegmentRef) -> None:
        seditor = SegmentEditor(track_editor=self, segment_ref=segment_ref)
        self.segments.insert(insert_index, seditor)
        seditor.setEnabled(self.isCurrent())
        seditor.resize(int(self.scaleX() * segment_ref.segment.duration.fraction), self.height())
        seditor.move(self.timeToX(segment_ref.time) - self.xOffset(), 0)
        seditor.show()
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

    def setXOffset(self, offset: int) -> int:
        dx = super().setXOffset(offset)
        for segment in self.segments:
            segment.move(self.timeToX(segment.startTime()) - self.xOffset(), 0)
        return dx

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)
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
