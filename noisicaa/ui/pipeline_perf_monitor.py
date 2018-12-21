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

import math
import time
from typing import Any, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

# pylint/mypy don't understand capnp modules.
from noisicaa.core import perf_stats_capnp  # type: ignore  # pylint: disable=no-name-in-module
from . import ui_base


class PipelinePerfMonitor(ui_base.AbstractPipelinePerfMonitor):
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.history = []  # type: List[perf_stats_capnp.PerfStats]
        self.realtime = True
        self.current_spans = None  # type: perf_stats_capnp.PerfStats
        self.max_fps = 20
        self.last_update = None  # type: float
        self.max_time_nsec = 100000000
        self.time_scale = 4096

        self.setWindowTitle("noisicaä - Pipeline Performance Monitor")
        self.resize(600, 300)

        self.gantt_font = QtGui.QFont()
        self.gantt_font.setPixelSize(10)

        self.pauseAction = QtWidgets.QAction("Play", self)
        self.pauseAction.setIcon(QtGui.QIcon.fromTheme('media-playback-pause'))
        self.pauseAction.triggered.connect(self.onToggleRealtime)

        self.zoomInAction = QtWidgets.QAction("Zoom In", self)
        self.zoomInAction.setIcon(QtGui.QIcon.fromTheme('zoom-in'))
        self.zoomInAction.triggered.connect(self.onZoomIn)

        self.zoomOutAction = QtWidgets.QAction("Zoom Out", self)
        self.zoomOutAction.setIcon(QtGui.QIcon.fromTheme('zoom-out'))
        self.zoomOutAction.triggered.connect(self.onZoomOut)

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.addAction(self.pauseAction)
        self.toolbar.addAction(self.zoomInAction)
        self.toolbar.addAction(self.zoomOutAction)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.gantt_scene = QtWidgets.QGraphicsScene()
        self.gantt_view = QtWidgets.QGraphicsView(self.gantt_scene, self)
        self.gantt_view.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.gantt_view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setCentralWidget(self.gantt_view)

        # TODO: somehow always ends up being shown...
        #self.setVisible(
        #    bool(self.app.settings.value('dialog/pipeline_perf_monitor/visible', False)))
        self.restoreGeometry(
            self.app.settings.value('dialog/pipeline_perf_monitor/geometry', b''))

    def storeState(self) -> None:
        s = self.app.settings
        s.beginGroup('dialog/pipeline_perf_monitor')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.endGroup()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.visibilityChanged.emit(True)
        super().showEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def onToggleRealtime(self) -> None:
        if self.realtime:
            self.realtime = False
            self.pauseAction.setIcon(
                QtGui.QIcon.fromTheme('media-playback-start'))
        else:
            self.realtime = True
            self.pauseAction.setIcon(
                QtGui.QIcon.fromTheme('media-playback-start'))

    def onZoomIn(self) -> None:
        self.time_scale *= 2
        self.updateGanttScene(self.current_spans)

    def onZoomOut(self) -> None:
        if self.time_scale > 1:
            self.time_scale //= 2
        self.updateGanttScene(self.current_spans)

    def updateGanttScene(self, perf_data: perf_stats_capnp.PerfStats) -> None:
        if perf_data is None:
            return
        self.current_spans = perf_data

        loffset = 300

        self.gantt_scene.clear()

        spans = sorted(perf_data.spans, key=lambda span: span.startTimeNSec)

        if spans:
            self.max_time_nsec = max(
                99 * self.max_time_nsec // 100,
                max(span.endTimeNSec - spans[0].startTimeNSec
                    for span in spans))

        scale = self.time_scale / 1e9
        tick_nsec = 10 ** int(math.log10(self.max_time_nsec))
        max_time_nsec = tick_nsec * (
            (self.max_time_nsec + tick_nsec - 1) // tick_nsec)

        line = QtWidgets.QGraphicsLineItem()
        line.setLine(loffset, 0, loffset + scale * max_time_nsec, 0)
        self.gantt_scene.addItem(line)

        for t in range(0, max_time_nsec + 1, tick_nsec // 10):
            x = loffset + scale * t
            line = QtWidgets.QGraphicsLineItem()
            if t % tick_nsec == 0:
                line.setLine(x, 0, x, 10)

                label = QtWidgets.QGraphicsTextItem()
                label.setFont(self.gantt_font)
                if t == 0:
                    label.setPlainText('0')
                elif tick_nsec >= 1000000:
                    label.setPlainText('%dms' % (t // 1000000))
                elif tick_nsec >= 1000:
                    label.setPlainText('%dus' % (t // 1000))
                else:
                    label.setPlainText('%dns' % t)
                if t < max_time_nsec:
                    label.setPos(x, 0)
                else:
                    label.setPos(x - label.boundingRect().width(), 0)
                self.gantt_scene.addItem(label)
            else:
                line.setLine(x, 0, x, 4)
            self.gantt_scene.addItem(line)

        if not spans:
            return

        timebase = spans[0].startTimeNSec
        y = 20
        for span in spans:
            label = QtWidgets.QGraphicsTextItem()
            label.setFont(self.gantt_font)
            label.setPlainText(span.name)
            label.setPos(0, y - 4)
            self.gantt_scene.addItem(label)

            x = loffset + scale * (span.startTimeNSec - timebase)
            w = max(1, scale * (span.endTimeNSec - span.startTimeNSec))

            bar = QtWidgets.QGraphicsRectItem()
            bar.setRect(x, y, w, 14)
            bar.setBrush(QtGui.QBrush(Qt.black))
            self.gantt_scene.addItem(bar)

            y += 16

        self.gantt_view.setSceneRect(
            -10, -10, loffset + scale * max_time_nsec + 20, y + 20)

    def addPerfData(self, perf_data: perf_stats_capnp.PerfStats) -> None:
        self.history.append(perf_data)
        num_purge = len(self.history) - 10000
        if num_purge > 0:
            del self.history[:num_purge]

        if self.realtime and self.isVisible():
            now = time.time()
            if self.last_update is None or now - self.last_update > 1.0 / self.max_fps:
                self.updateGanttScene(perf_data)
                self.last_update = now
