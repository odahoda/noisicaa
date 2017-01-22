#!/usr/bin/python3

import functools
import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class SampleItem(object):
    def __init__(self, track_item=None, sample=None):
        self.__track_item = track_item
        self.__sample = sample

        self.__render_result = ('init', )
        self.__highlighted = False

        self.__pos = QtCore.QPoint(
            self.__track_item.timeposToX(self.__sample.timepos), 0)
        self.__width = 50

        self.__listeners = [
            self.__sample.listeners.add('timepos', self.onTimeposChanged),
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

    def onTimeposChanged(self, old_timepos, new_timepos):
        self.__pos = QtCore.QPoint(
            self.__track_item.timeposToX(new_timepos), 0)
        self.__track_item.rectChanged.emit(self.__track_item.sheetRect())

    def setHighlighted(self, highlighted):
        if highlighted != self.__highlighted:
            self.__highlighted = highlighted
            self.__track_item.rectChanged.emit(
                self.rect().translated(self.__track_item.sheetTopLeft()))

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
        self.__track_item.rectChanged.emit(self.__track_item.sheetRect())

    def purgePaintCaches(self):
        self.__render_result = ('init', )
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


class SampleTrackEditorItemImpl(base_track_item.BaseTrackEditorItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__samples = []
        self.__listeners = []

        self.__playback_timepos = None
        self.__highlighted_sample = None
        self.__mouse_pos = None
        self.__moving_sample = None
        self.__moving_sample_original_pos = None
        self.__moving_sample_offset = None

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

    def supportedTools(self):
        return {
            tools.Tool.POINTER,
        }

    def defaultTool(self):
        return tools.Tool.POINTER

    def updateSize(self):
        width = 20
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width += int(self.scaleX() * measure.duration)
        self.setSize(QtCore.QSize(width, 120))

    def timeposToX(self, timepos):
        x = 10
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if timepos <= measure.duration:
                return x + int(width * timepos / measure.duration)

            x += width
            timepos -= measure.duration

        return x

    def xToTimepos(self, x):
        x -= 10
        timepos = music.Duration(0, 1)
        if x <= 0:
            return timepos

        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if x <= width:
                return music.Duration(timepos + measure.duration * music.Duration(int(x), width))

            timepos += measure.duration
            x -= width

        return music.Duration(timepos)

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
        self.rectChanged.emit(self.sheetRect())

    def removeSample(self, remove_index, sample):
        item = self.__samples.pop(remove_index)
        item.close()
        self.rectChanged.emit(self.sheetRect())

    def setPlaybackPos(self, timepos):
        if self.__playback_timepos is not None:
            x = self.timeposToX(self.__playback_timepos)
            self.rectChanged.emit(
                QtCore.QRect(self.sheetLeft() + x, self.sheetTop(), 2, self.height()))

        self.__playback_timepos = timepos

        if self.__playback_timepos is not None:
            x = self.timeposToX(self.__playback_timepos)
            self.rectChanged.emit(
                QtCore.QRect(self.sheetLeft() + x, self.sheetTop(), 2, self.height()))


    def setHighlightedSample(self, sample):
        if sample is self.__highlighted_sample:
            return

        if self.__highlighted_sample is not None:
            self.__highlighted_sample.setHighlighted(False)
            self.__highlighted_sample = None

        if sample is not None:
            sample.setHighlighted(True)
            self.__highlighted_sample = sample

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
        self.rectChanged.emit(self.sheetRect())

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        self._track_item.buildContextMenu(menu)
        self.buildContextMenu(menu)

        menu.exec_(event.screenPos())
        event.accept()

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        timepos = self.xToTimepos(pos.x())

        add_sample_action = QtWidgets.QAction(
            "Add sample...", menu,
            statusTip="Add a sample to the track.",
            triggered=functools.partial(self.onAddSample, timepos))
        menu.addAction(add_sample_action)

    def onAddSample(self, timepos):
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
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
            timepos=timepos, path=path)

    def leaveEvent(self, evt):
        self.__mouse_pos = None
        self.setHighlightedSample(None)
        super().leaveEvent(evt)

    def mousePressEvent(self, evt):
        self.__mouse_pos = evt.pos()

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self.__highlighted_sample is not None):
            self.__moving_sample = self.__highlighted_sample
            self.__moving_sample_original_pos = self.__moving_sample.pos()
            self.__moving_sample_offset = evt.pos() - self.__moving_sample.pos()

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self.__highlighted_sample is not None):
            self.send_command_async(
                self.track.id,
                'RemoveSample',
                sample_id=self.__highlighted_sample.sample_id)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__moving_sample is not None:
            self.setSamplePos(self.__moving_sample, self.__moving_sample_original_pos)
            self.__moving_sample = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        self.__mouse_pos = evt.pos()

        if self.__moving_sample is not None:
            new_pos = QtCore.QPoint(
                evt.pos().x() - self.__moving_sample_offset.x(),
                self.__moving_sample_original_pos.y())

            if new_pos.x() < 10:
                new_pos.setX(10)
            elif new_pos.x() > self.width() - 10 - self.__moving_sample.width():
                new_pos.setX(self.width() - 10 - self.__moving_sample.width())

            self.setSamplePos(self.__moving_sample, new_pos)

            evt.accept()
            return

        self.updateHighlightedSample()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        self.__mouse_pos = evt.pos()

        if evt.button() == Qt.LeftButton and self.__moving_sample is not None:
            pos = self.__moving_sample.pos()
            self.__moving_sample = None

            self.send_command_async(
                self.track.id,
                'MoveSample',
                sample_id=self.__highlighted_sample.sample_id,
                timepos=self.xToTimepos(pos.x()))

            evt.accept()
            return

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
        timepos = music.Duration()
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if x + width > paint_rect.x() and x < paint_rect.x() + paint_rect.width():
                if mref.is_first:
                    painter.fillRect(x, 0, 2, self.height(), QtGui.QColor(160, 160, 160))
                else:
                    painter.fillRect(x, 0, 1, self.height(), QtGui.QColor(160, 160, 160))

                for i in range(1, measure.time_signature.upper):
                    pos = int(width * i / measure.time_signature.lower)
                    painter.fillRect(x + pos, 0, 1, self.height(), QtGui.QColor(200, 200, 200))

            x += width
            timepos += measure.duration

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

        if self.__playback_timepos is not None:
            pos = self.timeposToX(self.__playback_timepos)
            painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))


class SampleTrackEditorItem(ui_base.ProjectMixin, SampleTrackEditorItemImpl):
    pass
