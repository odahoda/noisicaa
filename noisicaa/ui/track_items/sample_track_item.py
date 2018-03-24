#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

# TODO: mypy-unclean

import fractions
import functools
import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class EditSamplesTool(tools.ToolBase):
    def __init__(self, **kwargs):
        super().__init__(
            type=tools.ToolType.EDIT_SAMPLES,
            group=tools.ToolGroup.EDIT,
            **kwargs)

        self.__moving_sample = None
        self.__moving_sample_original_pos = None
        self.__moving_sample_offset = None

    def iconName(self):
        return 'edit-samples'

    def mousePressEvent(self, target, evt):
        assert isinstance(target, SampleTrackEditorItem), type(target).__name__

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and target.highlightedSample() is not None):
            self.__moving_sample = target.highlightedSample()
            self.__moving_sample_original_pos = self.__moving_sample.pos()
            self.__moving_sample_offset = evt.pos() - self.__moving_sample.pos()

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and target.highlightedSample() is not None):
            self.send_command_async(
                target.track.id,
                'RemoveSample',
                sample_id=target.highlightedSample().sample_id)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__moving_sample is not None:
            target.setSamplePos(self.__moving_sample, self.__moving_sample_original_pos)
            self.__moving_sample = None
            evt.accept()
            return

        super().mousePressEvent(target, evt)

    def mouseMoveEvent(self, target, evt):
        if self.__moving_sample is not None:
            new_pos = QtCore.QPoint(
                evt.pos().x() - self.__moving_sample_offset.x(),
                self.__moving_sample_original_pos.y())

            if new_pos.x() < 10:
                new_pos.setX(10)
            elif new_pos.x() > target.width() - 10 - self.__moving_sample.width():
                new_pos.setX(target.width() - 10 - self.__moving_sample.width())

            target.setSamplePos(self.__moving_sample, new_pos)

            evt.accept()
            return

        target.updateHighlightedSample()

        super().mouseMoveEvent(target, evt)

    def mouseReleaseEvent(self, target, evt):
        if evt.button() == Qt.LeftButton and self.__moving_sample is not None:
            pos = self.__moving_sample.pos()
            self.__moving_sample = None

            self.send_command_async(
                target.track.id,
                'MoveSample',
                sample_id=target.highlightedSample().sample_id,
                time=target.xToTime(pos.x()))

            evt.accept()
            return

        super().mouseReleaseEvent(target, evt)


class SampleTrackToolBox(tools.ToolBox):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.addTool(EditSamplesTool(**self.context_args))


class SampleItem(object):
    def __init__(self, track_item=None, sample=None):
        self.__track_item = track_item
        self.__sample = sample

        self.__render_result = ('init', )
        self.__highlighted = False

        self.__pos = QtCore.QPoint(
            self.__track_item.timeToX(self.__sample.time), 0)
        self.__width = 50

        self.__listeners = [
            self.__sample.listeners.add('time', self.onTimeChanged),
        ]

    def close(self):
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    @property
    def sample_id(self):
        return self.__sample.id

    def scaleX(self):
        return self.__track_item.scaleX()

    def width(self):
        return self.__width

    def height(self):
        return self.__track_item.height()

    def size(self):
        return QtCore.QSize(self.width(), self.height())

    def pos(self):
        return self.__pos

    def setPos(self, pos):
        self.__pos = pos

    def rect(self):
        return QtCore.QRect(self.pos(), self.size())

    def onTimeChanged(self, old_time, new_time):
        self.__pos = QtCore.QPoint(
            self.__track_item.timeToX(new_time), 0)
        self.__track_item.rectChanged.emit(self.__track_item.viewRect())

    def setHighlighted(self, highlighted):
        if highlighted != self.__highlighted:
            self.__highlighted = highlighted
            self.__track_item.rectChanged.emit(
                self.rect().translated(self.__track_item.viewTopLeft()))

    def renderSample(self, render_result):
        status, *args = render_result
        if status == 'waiting':
            self.__width = 50

        elif status == 'broken':
            self.__width = 50

        elif status == 'highres':
            samples, = args
            self.__width = len(samples)

        elif status == 'rms':
            samples, = args
            self.__width = len(samples)

        self.__render_result = render_result
        self.__track_item.rectChanged.emit(self.__track_item.viewRect())

    def purgePaintCaches(self):
        self.__render_result = ('init', )
        self.__pos = QtCore.QPoint(
            self.__track_item.timeToX(self.__sample.time), 0)
        self.__width = 50

    def paint(self, painter, paint_rect):
        status, *args = self.__render_result

        if status in ('init', 'waiting'):
            if status == 'init':
                self.__track_item.send_command_async(
                    self.__sample.id, 'RenderSample',
                    scale_x=self.scaleX(),
                    callback=self.renderSample)
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

        elif status == 'highres':
            samples, = args
            ycenter = self.height() // 2

            if self.__highlighted:
                painter.setPen(QtGui.QColor(0, 0, 120))
            else:
                painter.setPen(Qt.black)

            painter.drawLine(0, 0, 0, self.height() - 1)
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height() - 1)
            painter.drawLine(0, ycenter, self.width() - 1, ycenter)

            p_y = None
            for x, smpl in enumerate(samples):
                y = max(0, min(self.height() - 1, int(self.height() * (1.0 - smpl) / 2.0)))
                if x > 0:
                    painter.drawLine(x - 1, p_y, x, y)
                p_y = y

        elif status == 'rms':
            samples, = args
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


class SampleTrackEditorItem(base_track_item.BaseTrackEditorItem):
    toolBoxClass = SampleTrackToolBox

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__samples = []
        self.__listeners = []

        self.__playback_time = None
        self.__highlighted_sample = None
        self.__mouse_pos = None

        for sample in self.track.samples:
            self.addSample(len(self.__samples), sample)

        self.__listeners.append(self.track.listeners.add(
            'samples', self.onSamplesChanged))

        self.updateSize()

    def close(self):
        for item in self.__samples:
            item.close()
        self.__samples.clear()

        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        super().close()

    def updateSize(self):
        width = 20
        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width += int(self.scaleX() * measure.duration.fraction)
        self.setSize(QtCore.QSize(width, 120))

    def timeToX(self, time):
        x = 10
        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if time - measure.duration <= audioproc.MusicalTime(0, 1):
                return x + int(width * (time / measure.duration).fraction)

            x += width
            time -= measure.duration

        return x

    def xToTime(self, x):
        x -= 10
        time = audioproc.MusicalTime(0, 1)
        if x <= 0:
            return time

        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if x <= width:
                return time + measure.duration * fractions.Fraction(int(x), width)

            time += measure.duration
            x -= width

        return time

    def onSamplesChanged(self, action, *args):
        if action == 'insert':
            insert_index, sample = args
            self.addSample(insert_index, sample)

        elif action == 'delete':
            remove_index, sample = args
            self.removeSample(remove_index, sample)

        else:
            raise ValueError("Unknown action %r" % action)

    def addSample(self, insert_index, sample):
        item = SampleItem(track_item=self, sample=sample)
        self.__samples.insert(insert_index, item)
        self.rectChanged.emit(self.viewRect())

    def removeSample(self, remove_index, sample):
        item = self.__samples.pop(remove_index)
        item.close()
        self.rectChanged.emit(self.viewRect())

    def setPlaybackPos(self, time):
        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.rectChanged.emit(
                QtCore.QRect(self.viewLeft() + x, self.viewTop(), 2, self.height()))

        self.__playback_time = time

        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.rectChanged.emit(
                QtCore.QRect(self.viewLeft() + x, self.viewTop(), 2, self.height()))

    def setHighlightedSample(self, sample):
        if sample is self.__highlighted_sample:
            return

        if self.__highlighted_sample is not None:
            self.__highlighted_sample.setHighlighted(False)
            self.__highlighted_sample = None

        if sample is not None:
            sample.setHighlighted(True)
            self.__highlighted_sample = sample

    def highlightedSample(self):
        return self.__highlighted_sample

    def updateHighlightedSample(self):
        if self.__mouse_pos is None:
            self.setHighlightedSample(None)
            return

        closest_sample = None
        closest_dist = None
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

    def setSamplePos(self, sample, pos):
        sample.setPos(pos)
        self.rectChanged.emit(self.viewRect())

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        self._track_item.buildContextMenu(menu)
        self.buildContextMenu(menu)

        menu.exec_(event.screenPos())
        event.accept()

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        time = self.xToTime(pos.x())

        add_sample_action = QtWidgets.QAction(
            "Add sample...", menu,
            statusTip="Add a sample to the track.",
            triggered=functools.partial(self.onAddSample, time))
        menu.addAction(add_sample_action)

    def onAddSample(self, time):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self.window,
            caption="Add Sample to track \"%s\"" % self.track.name,
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;Wav files (*.wav)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        self.send_command_async(
            self.track.id, 'AddSample',
            time=time, path=path)

    def leaveEvent(self, evt):
        self.__mouse_pos = None
        self.setHighlightedSample(None)
        super().leaveEvent(evt)

    def mousePressEvent(self, evt):
        self.__mouse_pos = evt.pos()
        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        self.__mouse_pos = evt.pos()
        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        self.__mouse_pos = evt.pos()
        super().mouseReleaseEvent(evt)

    def purgePaintCaches(self):
        super().purgePaintCaches()
        for item in self.__samples:
            item.purgePaintCaches()

    def paint(self, painter, paint_rect):
        super().paint(painter, paint_rect)

        painter.setPen(QtGui.QColor(160, 160, 160))
        painter.drawLine(
            10, self.height() // 2,
            self.width() - 11, self.height() // 2)

        x = 10
        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if x + width > paint_rect.x() and x < paint_rect.x() + paint_rect.width():
                if mref.is_first:
                    painter.fillRect(x, 0, 2, self.height(), QtGui.QColor(160, 160, 160))
                else:
                    painter.fillRect(x, 0, 1, self.height(), QtGui.QColor(160, 160, 160))

                for i in range(1, measure.time_signature.upper):
                    pos = int(width * i / measure.time_signature.lower)
                    painter.fillRect(x + pos, 0, 1, self.height(), QtGui.QColor(200, 200, 200))

            x += width

        painter.fillRect(x - 2, 0, 2, self.height(), QtGui.QColor(160, 160, 160))

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
