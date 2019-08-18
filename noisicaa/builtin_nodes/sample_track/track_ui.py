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

import asyncio
import fractions
import functools
import logging
from typing import Any, List, Tuple, Sequence

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui.track_list import base_track_editor
from noisicaa.ui.track_list import time_view_mixin
from noisicaa.ui.track_list import tools
from . import ipc_pb2
from . import model

logger = logging.getLogger(__name__)


class EditSamplesTool(tools.ToolBase):
    track = None  # type: SampleTrackEditor

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.EDIT_SAMPLES,
            group=tools.ToolGroup.EDIT,
            **kwargs)

        self.__moving_sample = None  # type: SampleItem
        self.__moving_sample_original_pos = None  # type: QtCore.QPoint
        self.__moving_sample_offset = None  # type: QtCore.QPoint

    def iconName(self) -> str:
        return 'edit-samples'

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self.track.highlightedSample() is not None):
            self.__moving_sample = self.track.highlightedSample()
            self.__moving_sample_original_pos = self.__moving_sample.pos()
            self.__moving_sample_offset = evt.pos() - self.__moving_sample.pos()

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self.track.highlightedSample() is not None):
            with self.project.apply_mutations('%s: Remove sample' % self.track.track.name):
                self.track.track.delete_sample(self.track.highlightedSample().sample)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__moving_sample is not None:
            self.track.setSamplePos(self.__moving_sample, self.__moving_sample_original_pos)
            self.__moving_sample = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__moving_sample is not None:
            new_pos = QtCore.QPoint(
                evt.pos().x() - self.__moving_sample_offset.x(),
                self.__moving_sample_original_pos.y())

            if new_pos.x() < 10:
                new_pos.setX(10)
            elif new_pos.x() > self.track.width() - 10 - self.__moving_sample.width():
                new_pos.setX(self.track.width() - 10 - self.__moving_sample.width())

            self.track.setSamplePos(self.__moving_sample, new_pos)

            evt.accept()
            return

        self.track.updateHighlightedSample()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__moving_sample is not None:
            pos = self.__moving_sample.pos()
            self.__moving_sample = None

            with self.project.apply_mutations('%s: Move sample' % self.track.track.name):
                self.track.highlightedSample().sample.time = self.track.xToTime(pos.x())

            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class SampleTrackToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(EditSamplesTool)


class SampleItem(core.AutoCleanupMixin, object):
    def __init__(self, track_editor: 'SampleTrackEditor', sample: model.SampleRef) -> None:
        super().__init__()

        self.__track_editor = track_editor
        self.__sample = sample

        self.__render_result = ('init', )  # type: Tuple[Any, ...]
        self.__highlighted = False

        self.__pos = QtCore.QPoint(
            self.__track_editor.timeToX(self.__sample.time), 0)
        self.__width = 50

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)
        self.__listeners.add(self.__sample.time_changed.add(self.onTimeChanged))

    @property
    def sample(self) -> model.SampleRef:
        return self.__sample

    @property
    def sample_id(self) -> int:
        return self.__sample.id

    def scaleX(self) -> fractions.Fraction:
        return self.__track_editor.scaleX()

    def width(self) -> int:
        return self.__width

    def height(self) -> int:
        return self.__track_editor.height()

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.width(), self.height())

    def pos(self) -> QtCore.QPoint:
        return self.__pos

    def setPos(self, pos: QtCore.QPoint) -> None:
        self.__pos = pos

    def rect(self) -> QtCore.QRect:
        return QtCore.QRect(self.pos(), self.size())

    def onTimeChanged(self, change: music.PropertyValueChange[audioproc.MusicalTime]) -> None:
        self.__pos = QtCore.QPoint(
            self.__track_editor.timeToX(change.new_value), 0)
        self.__track_editor.update()

    def setHighlighted(self, highlighted: bool) -> None:
        if highlighted != self.__highlighted:
            self.__highlighted = highlighted
            self.__track_editor.update()

    def renderSample(self, task: asyncio.Task) -> None:
        response = down_cast(ipc_pb2.RenderSampleResponse, task.result())

        if response.broken:
            self.__width = 50
            self.__render_result = ('broken',)

        else:
            self.__width = len(response.rms)
            self.__render_result = ('rms', list(response.rms))

        self.__track_editor.update()

    def purgePaintCaches(self) -> None:
        self.__render_result = ('init', )
        self.__pos = QtCore.QPoint(
            self.__track_editor.timeToX(self.__sample.time), 0)
        self.__width = 50

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        status = self.__render_result[0]

        if status in ('init', 'waiting'):
            if status == 'init':
                task = self.__track_editor.event_loop.create_task(
                    model.render_sample(self.__sample, self.scaleX()))
                task.add_done_callback(self.renderSample)

                self.__render_result = ('waiting', )

            painter.fillRect(
                0, 0, self.width(), self.height(),
                QtGui.QColor(220, 255, 220))

            painter.setPen(Qt.black)
            painter.drawText(3, 20, "Loading...")

        elif status == 'broken':
            painter.fillRect(
                0, 0, self.width(), self.height(),
                QtGui.QColor(255, 100, 100))

            painter.setPen(Qt.black)
            painter.drawText(3, 20, "Broken")

        elif status == 'rms':
            samples = self.__render_result[1]  # type: Sequence[float]
            ycenter = self.height() // 2

            if self.__highlighted:
                painter.setPen(QtGui.QColor(0, 0, 120))
            else:
                painter.setPen(Qt.black)

            painter.drawLine(0, 0, 0, self.height() - 1)
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height() - 1)
            painter.drawLine(0, ycenter, self.width() - 1, ycenter)

            for x, smpl in enumerate(
                    samples[paint_rect.x():paint_rect.x() + paint_rect.width()],
                    paint_rect.x()):
                h = min(self.height(), int(self.height() * smpl / 2.0))
                painter.drawLine(x, ycenter - h // 2, x, ycenter + h // 2)


class SampleTrackEditor(time_view_mixin.ContinuousTimeMixin, base_track_editor.BaseTrackEditor):
    def __init__(self, **kwargs: Any) -> None:
        self.__samples = []  # type: List[SampleItem]

        super().__init__(**kwargs)

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__playback_time = None  # type: audioproc.MusicalTime
        self.__highlighted_sample = None  # type: SampleItem
        self.__mouse_pos = None  # type: QtCore.QPoint

        for sample in self.track.samples:
            self.addSample(len(self.__samples), sample)

        self.__listeners.add(self.track.samples_changed.add(self.onSamplesChanged))

        self.setFixedHeight(120)

    @property
    def track(self) -> model.SampleTrack:
        return down_cast(model.SampleTrack, super().track)

    def cleanup(self) -> None:
        for item in self.__samples:
            item.cleanup()
        self.__samples.clear()

        super().cleanup()

    def createToolBox(self) -> SampleTrackToolBox:
        return SampleTrackToolBox(track=self, context=self.context)

    def onSamplesChanged(self, change: music.PropertyListChange[model.SampleRef]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.addSample(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.removeSample(change.index, change.old_value)

        else:
            raise TypeError(type(change))

    def addSample(self, insert_index: int, sample: model.SampleRef) -> None:
        item = SampleItem(track_editor=self, sample=sample)
        self.__samples.insert(insert_index, item)
        self.update()

    def removeSample(self, remove_index: int, sample: model.SampleRef) -> None:
        item = self.__samples.pop(remove_index)
        item.cleanup()
        self.update()

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.update(x - self.xOffset(), 0, 2, self.height())

        self.__playback_time = time

        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.update(x - self.xOffset(), 0, 2, self.height())

    def setHighlightedSample(self, sample: SampleItem) -> None:
        if sample is self.__highlighted_sample:
            return

        if self.__highlighted_sample is not None:
            self.__highlighted_sample.setHighlighted(False)
            self.__highlighted_sample = None

        if sample is not None:
            sample.setHighlighted(True)
            self.__highlighted_sample = sample

    def highlightedSample(self) -> SampleItem:
        return self.__highlighted_sample

    def updateHighlightedSample(self) -> None:
        if self.__mouse_pos is None:
            self.setHighlightedSample(None)
            return

        closest_sample = None  # type: SampleItem
        closest_dist = None  # type: int
        for sample in self.__samples:
            if self.__mouse_pos.x() < sample.pos().x():
                dist = sample.pos().x() - self.__mouse_pos.x()
            elif self.__mouse_pos.x() > sample.pos().x() + sample.width():
                dist = self.__mouse_pos.x() - (sample.pos().x() + sample.width())
            else:
                dist = 0

            if dist < 20 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_sample = sample

        self.setHighlightedSample(closest_sample)

    def setSamplePos(self, sample: SampleItem, pos: QtCore.QPoint) -> None:
        sample.setPos(pos)
        self.update()

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        super().buildContextMenu(menu, pos)

        time = self.xToTime(pos.x())

        add_sample_action = QtWidgets.QAction("Add sample...", menu)
        add_sample_action.setStatusTip("Add a sample to the track.")
        add_sample_action.triggered.connect(functools.partial(self.onAddSample, time))
        menu.addAction(add_sample_action)

    def onAddSample(self, time: audioproc.MusicalTime) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self.project_view,
            caption="Add Sample to track \"%s\"" % self.track.name,
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;Wav files (*.wav)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        with self.project.apply_mutations('%s: Create sample' % self.track.name):
            self.track.create_sample(time, path)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.__mouse_pos = None
        self.setHighlightedSample(None)
        super().leaveEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mouseReleaseEvent(evt)

    def purgePaintCaches(self) -> None:
        super().purgePaintCaches()
        for item in self.__samples:
            item.purgePaintCaches()

    def _paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        painter.setPen(QtGui.QColor(160, 160, 160))
        painter.drawLine(
            self.timeToX(audioproc.MusicalTime(0, 1)), self.height() // 2,
            self.timeToX(self.projectEndTime()), self.height() // 2)

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

        for item in self.__samples:
            sample_rect = item.rect().intersected(paint_rect)
            if not sample_rect.isEmpty():
                painter.save()
                try:
                    painter.setClipRect(sample_rect)
                    painter.translate(item.pos())
                    item.paint(painter, sample_rect.translated(-item.pos()))
                finally:
                    painter.restore()

        if self.__playback_time is not None:
            pos = self.timeToX(self.__playback_time)
            painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))
