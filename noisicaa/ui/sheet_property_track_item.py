#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item

logger = logging.getLogger(__name__)


class SheetPropertyMeasureLayout(base_track_item.MeasureLayout):
    pass


class SheetPropertyMeasureItemImpl(base_track_item.MeasureItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bpm = None
        self.bpm_proxy = None

        self._layers[base_track_item.Layer.MAIN] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EVENTS] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EDIT] = QGraphicsGroup()

        if self._measure is not None:
            self.bpm_editor = QtWidgets.QSpinBox(
                suffix=' bpm',
                minimum=1, maximum=1000,
                singleStep=1, accelerated=True)
            self.bpm_editor.setValue(self._measure.bpm)
            self.bpm_editor.valueChanged.connect(self.onBPMEdited)
            self.bpm_editor.editingFinished.connect(self.onBPMClose)
            self.bpm_editor.setVisible(False)

            self.bpm_proxy = QtWidgets.QGraphicsProxyWidget(
                self._layers[base_track_item.Layer.EDIT])
            self.bpm_proxy.setWidget(self.bpm_editor)
            self.bpm_proxy.setZValue(1)

            self.playback_pos = QtWidgets.QGraphicsLineItem(
                self._layers[base_track_item.Layer.EVENTS])
            self.playback_pos.setVisible(False)
            self.playback_pos.setLine(0, 0, 0, 20)
            pen = QtGui.QPen(Qt.black)
            pen.setWidth(3)
            self.playback_pos.setPen(pen)

    def computeLayout(self):
        width = 100
        height_above = 10
        height_below = 10

        layout = SheetPropertyMeasureLayout()
        layout.size = QtCore.QSize(width, height_above + height_below)
        layout.baseline = height_above
        return layout

    def _updateMeasureInternal(self):
        assert self._layout.width > 0 and self._layout.height > 0

        layer = self._layers[base_track_item.Layer.MAIN]
        self._sheet_view.clearLayer(layer)

        if self._measure is not None:
            black = Qt.black
        else:
            black = QtGui.QColor(200, 200, 200)

        line = QtWidgets.QGraphicsLineItem(layer)
        line.setLine(0, self._layout.baseline,
                     self._layout.width, self._layout.baseline)
        line.setPen(black)

        if self._measure is not None:
            for i in range(self._measure.time_signature.upper):
                x = int(i * self._layout.width / self._measure.time_signature.upper)
                tick = QtWidgets.QGraphicsLineItem(layer)
                tick.setLine(x, self._layout.baseline,
                             x, self._layout.baseline + 10)
                tick.setPen(black)

            bpm = self.bpm = QtWidgets.QGraphicsSimpleTextItem(layer)
            bpm.setText('%d bpm' % self._measure.bpm)
            bpm.setPos(3, self._layout.baseline - bpm.boundingRect().height())
            bpm.setBrush(black)

            line = QtWidgets.QGraphicsLineItem(layer)
            line.setLine(0, self._layout.baseline - bpm.boundingRect().height(),
                         0, self._layout.baseline)
            line.setPen(black)

            self.bpm_proxy.setPos(
                3, self._layout.baseline - bpm.boundingRect().height())

    def mousePressEvent(self, event):
        if self._measure is None:
            self.send_command_async(
                self._sheet_view.sheet.id,
                'InsertMeasure', tracks=[], pos=-1)
            event.accept()
            return

        if self._layout.width <= 0 or self._layout.height <= 0:
            logger.warning("mousePressEvent without valid layout.")
            return

        self.bpm_editor.setVisible(True)
        self.bpm_editor.selectAll()
        self.bpm_editor.setFocus()

        return super().mousePressEvent(event)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

    def onBPMEdited(self, value):
        self.send_command_async(
            self._measure.id, 'SetBPM', bpm=value)
        self.bpm.setText('%d bpm' % value)

    def onBPMClose(self):
        self.bpm_editor.setVisible(False)

    def clearPlaybackPos(self):
        self.playback_pos.setVisible(False)

    def setPlaybackPos(
            self, sample_pos, num_samples, start_tick, end_tick, first):
        if first:
            assert 0 <= start_tick < self._measure.duration.ticks
            assert self._layout.width > 0 and self._layout.height > 0

            pos = (
                self._layout.width
                * start_tick
                / self._measure.duration.ticks)
            self.playback_pos.setPos(pos, 0)
            self.playback_pos.setVisible(True)


class SheetPropertyMeasureItem(
        ui_base.ProjectMixin, SheetPropertyMeasureItemImpl):
    pass


class SheetPropertyTrackItemImpl(base_track_item.TrackItemImpl):
    measure_item_cls = SheetPropertyMeasureItem


class SheetPropertyTrackItem(
        ui_base.ProjectMixin, SheetPropertyTrackItemImpl):
    pass
