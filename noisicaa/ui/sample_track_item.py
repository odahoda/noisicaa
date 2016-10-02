#!/usr/bin/python3

from fractions import Fraction
import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.music import model
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item
from . import layout

logger = logging.getLogger(__name__)


class SampleTrackLayout(layout.TrackLayout):
    def __init__(self, track):
        super().__init__()
        self._track = track
        self._widths = []
        self._scale_x = None

    def compute(self, scale_x):
        self._scale_x = scale_x

        timepos = Fraction(0, 1)
        x = 0

        for mref in self._track.sheet.property_track.measure_list:
            measure = mref.measure

            end_timepos = timepos + measure.duration
            end_x = int(scale_x * end_timepos)
            width = end_x - x

            self._widths.append(width)

            timepos = end_timepos
            x = end_x

    @property
    def widths(self):
        return self._widths

    @property
    def width(self):
        return sum(self.widths)

    @property
    def height(self):
        return 120

    @property
    def scale_x(self):
        return self._scale_x


class SampleItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent=None, group=None, sample=None):
        super().__init__(parent=parent)

        self._group = group
        self._sample = sample

        self._overlay = None

        self._listeners = [
            self._sample.listeners.add('timepos', self.onTimeposChanged),
        ]

        self.setRect(0, 0, 50, self._group.height)
        self.setPen(Qt.black)
        self.setBrush(Qt.white)

        overlay = QtWidgets.QGraphicsSimpleTextItem(self)
        overlay.setText("Rendering...")
        self.setOverlay(overlay)

    @property
    def sample_id(self):
        return self._sample.id

    @property
    def width(self):
        return self.rect().width()

    def close(self):
        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def onTimeposChanged(self, old_timepos, new_timepos):
        self._group.setSamplePos(
            self,
            QtCore.QPointF(self._group.timeposToX(new_timepos), self.pos().y()))

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setBrush(Qt.white)

    def setOverlay(self, overlay):
        if self._overlay is not None:
            if self._overlay.scene() is not None:
                self._overlay.scene().removeItem(self._overlay)
            self._overlay = None

        self._overlay = overlay

    def renderSample(self, render_result):
        status, *args = render_result
        if status == 'broken':
            self.setRect(0, 0, 50, self._group.height)

            overlay = QtWidgets.QGraphicsSimpleTextItem(self)
            overlay.setText("Broken")
            self.setOverlay(overlay)

        elif status == 'highres':
            samples, = args

            self.setRect(0, 0, len(samples), self._group.height)
            pixmap = QtGui.QPixmap(len(samples), self._group.height)
            pixmap.fill(Qt.white)
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QColor(200, 200, 200))
            painter.drawLine(0, self._group.height // 2, len(samples) - 1, self._group.height // 2)

            painter.setPen(Qt.black)
            p_y = None
            for x, smpl in enumerate(samples):
                y = max(0, min(self._group.height - 1, int(self._group.height * (1.0 - smpl) / 2.0)))
                if x > 0:
                    painter.drawLine(x - 1, p_y, x, y)
                p_y = y
            painter = None
            pixmap_item = QtWidgets.QGraphicsPixmapItem(pixmap, self)
            self.setOverlay(pixmap_item)

        elif status == 'rms':
            samples, = args

            ycenter = self._group.height // 2

            self.setRect(0, 0, len(samples), self._group.height)
            pixmap = QtGui.QPixmap(len(samples), self._group.height)
            pixmap.fill(Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QColor(200, 200, 200))
            painter.drawLine(0, ycenter, len(samples) - 1, ycenter)

            painter.setPen(Qt.black)
            for x, smpl in enumerate(samples):
                h = min(self._group.height, int(self._group.height * smpl / 2.0))
                painter.drawLine(x, ycenter - h // 2, x, ycenter + h // 2)

            painter = None
            pixmap_item = QtWidgets.QGraphicsPixmapItem(pixmap, self)
            self.setOverlay(pixmap_item)


class SampleGroup(ui_base.ProjectMixin, QGraphicsGroup):
    def __init__(
            self,
            track_item=None, size=None, widths=None, durations=None, scale_x=None,
            **kwargs):
        super().__init__(**kwargs)

        self._track_item = track_item
        self._track = track_item.track
        self._size = size
        self._widths = widths
        self._durations = durations
        self._scale_x = scale_x

        self._samples = []
        self._listeners = []

        self._highlighted_sample = None
        self._mouse_pos = None
        self._moving_sample = None
        self._moving_sample_original_pos = None
        self._moving_sample_offset = None

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.ArrowCursor)

        x = 0
        for width in self._widths:
            x += width

            l = QtWidgets.QGraphicsLineItem(self)
            l.setLine(x, 0, x, self.height)
            l.setPen(QtGui.QColor(240, 240, 240))

        frame = QtWidgets.QGraphicsRectItem(self)
        frame.setRect(0, 0, self.width, self.height)
        frame.setPen(QtGui.QColor(200, 200, 200))
        frame.setBrush(QtGui.QBrush(Qt.NoBrush))

        for sample in self._track.samples:
            self.addSample(len(self._samples), sample)

        self._listeners.append(self._track.listeners.add(
            'samples', self.onSamplesChanged))

    def close(self):
        for item in self._samples:
            item.close()
        self._samples.clear()

        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    @property
    def width(self):
        return self._size.width()

    @property
    def height(self):
        return self._size.height()

    def timeposToX(self, timepos):
        x = 0
        for width, duration in zip(self._widths, self._durations):
            if timepos <= duration:
                return x + int(width * timepos / duration)

            x += width
            timepos -= duration

        return x

    def xToTimepos(self, x):
        timepos = music.Duration(0, 1)
        for width, duration in zip(self._widths, self._durations):
            if x <= width:
                return music.Duration(timepos + duration * music.Duration(int(x), width))

            timepos += duration
            x -= width

        return timepos

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
        item = SampleItem(parent=self, group=self, sample=sample)
        item.setPos(self.timeposToX(sample.timepos), 0)
        self._samples.insert(insert_index, item)

        self.send_command_async(
            sample.id, 'RenderSample',
            scale_x=self._scale_x,
            callback=item.renderSample)

    def removeSample(self, remove_index, sample):
        item = self._samples.pop(remove_index)
        item.close()
        item.scene().removeItem(item)

    def setHighlightedSample(self, sample):
        if self._highlighted_sample is not None:
            self._highlighted_sample.setHighlighted(False)
            self._highlighted_sample = None

        if sample is not None:
            sample.setHighlighted(True)
            self._highlighted_sample = sample

    def updateHighlightedSample(self):
        if self._mouse_pos is None:
            self.setHighlightedSample(None)
            return

        closest_sample = None
        closest_dist = None
        for sample in self._samples:
            if self._mouse_pos.x() < sample.pos().x():
                dist = sample.pos().x() - self._mouse_pos.x()
            elif self._mouse_pos.x() > sample.pos().x() + sample.width:
                dist = self._mouse_pos.x() - (sample.pos().x() + sample.width)
            else:
                dist = 0

            if dist < 20 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_sample = sample

        self.setHighlightedSample(closest_sample)

    def setSamplePos(self, sample, pos):
        sample.setPos(pos)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        self._track_item.buildContextMenu(menu)
        self.buildContextMenu(menu)

        menu.exec_(event.screenPos())
        event.accept()

    def buildContextMenu(self, menu):
        add_sample_action = QtWidgets.QAction(
            "Add sample...", menu,
            statusTip="Add a sample to the track.",
            triggered=self.onAddSample)
        menu.addAction(add_sample_action)

    def onAddSample(self):
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self.window,
            caption="Add Sample to track \"%s\"" % self._track.name,
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;Wav files (*.wav)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        self.send_command_async(
            self._track.id, 'AddSample',
            timepos=music.Duration(0, 1), path=path)

    def hoverEnterEvent(self, evt):
        self.grabMouse()
        self._mouse_pos = evt.pos()
        super().hoverLeaveEvent(evt)

    def hoverLeaveEvent(self, evt):
        self.ungrabMouse()
        self._mouse_pos = None
        self.setHighlightedSample(None)
        super().hoverLeaveEvent(evt)

    def mousePressEvent(self, evt):
        self._mouse_pos = evt.pos()
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self._highlighted_sample is not None):
            self._moving_sample = self._highlighted_sample
            self._moving_sample_original_pos = self._moving_sample.pos()
            self._moving_sample_offset = evt.pos() - self._moving_sample.pos()

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self._highlighted_sample is not None):
            self.send_command_async(
                self._track.id,
                'RemoveSample',
                sample_id=self._highlighted_sample.sample_id)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self._moving_sample is not None:
            self.setSamplePos(self._moving_sample, self._moving_sample_original_pos)
            self._moving_sample = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        self._mouse_pos = evt.pos()
        if self._moving_sample is not None:
            new_pos = QtCore.QPointF(
                evt.pos().x() - self._moving_sample_offset.x(),
                self._moving_sample_original_pos.y())

            if new_pos.x() < 0:
                new_pos.setX(0)
            elif new_pos.x() > self.width - self._moving_sample.width:
                new_pos.setX(self.width - self._moving_sample.width)

            self.setSamplePos(self._moving_sample, new_pos)

            evt.accept()
            return

        self.updateHighlightedSample()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        self._mouse_pos = evt.pos()
        if evt.button() == Qt.LeftButton and self._moving_sample is not None:
            pos = self._moving_sample.pos()
            self._moving_sample = None

            self.send_command_async(
                self._track.id,
                'MoveSample',
                sample_id=self._highlighted_sample.sample_id,
                timepos=self.xToTimepos(pos.x()))

            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class SampleTrackItemImpl(base_track_item.TrackItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._group = None

    def close(self):
        super().close()

        if self._group is not None:
            self._group.close()
            self._group = None

    def getLayout(self):
        return SampleTrackLayout(self._track)

    def renderTrack(self, y, track_layout):
        layer = self._sheet_view.layers[base_track_item.Layer.MAIN]

        text = QtWidgets.QGraphicsSimpleTextItem(layer)
        text.setText("> %s" % self._track.name)
        text.setPos(0, y)

        if self._group is not None:
            self._group.close()
            self._group = None

        self._group = SampleGroup(
            parent=layer,
            track_item=self,
            size=QtCore.QSize(track_layout.width, track_layout.height - 20),
            widths=track_layout.widths,
            durations=[
                mref.measure.duration
                for mref in self._track.sheet.property_track.measure_list],
            scale_x=track_layout.scale_x,
            **self.context)
        self._group.setPos(0, y + 20)

    def setPlaybackPos(
            self, sample_pos, num_samples, start_measure_idx,
            start_measure_tick, end_measure_idx, end_measure_tick):
        pass


class SampleTrackItem(ui_base.ProjectMixin, SampleTrackItemImpl):
    pass
