#!/usr/bin/python

import functools
import math
import time
import uuid

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import ui_base

class StatGraph(QtWidgets.QWidget):
    def __init__(self, *, parent, name):
        super().__init__(parent)

        self.setMinimumHeight(200)
        self.setMaximumHeight(200)

        self.__name = name
        self.__id = uuid.uuid4().hex
        self.__timeseries_set = None

    def name(self):
        return self.__name

    def id(self):
        return self.__id

    def expression(self):
        return [
            ('SELECT', self.__name),
            ('RATE',)]

    def setTimeseriesSet(self, ts_set):
        self.__timeseries_set = ts_set
        self.update()

    def paintEvent(self, evt):
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), Qt.black)
        painter.setPen(Qt.white)
        painter.drawText(5, 16, str(self.__name))

        if self.__timeseries_set is not None:
            vmin = self.__timeseries_set.min()
            vmax = self.__timeseries_set.max()

            if vmax == vmin:
                vmin = vmin - 1
                vmax = vmax + 1

            for name, ts in self.__timeseries_set.items():
                px, py = None, None
                for idx, value in enumerate(ts):
                    x = self.width() - idx - 1
                    y = int((self.height() - 1) * (vmax - value.value) / (vmax - vmin))
                    if px is not None:
                        painter.drawLine(px, py, x, y)
                    px, py = x, y

        painter.end()


class StatMonitor(ui_base.CommonMixin, QtWidgets.QMainWindow):
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self, app):
        super().__init__(app=app)

        self.__update_timer = QtCore.QTimer(self)
        self.__update_timer.setInterval(1000)
        self.__update_timer.timeout.connect(self.onUpdate)

        self.__realtime = True
        self.__time_scale = 4096

        self.setWindowTitle("noisicaä - Stat Monitor")
        self.resize(600, 300)

        self.__pause_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('media-playback-pause'),
            "Play",
            self, triggered=self.onToggleRealtime)
        self.__zoom_in_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('zoom-in'),
            "Zoom In",
            self, triggered=self.onZoomIn)
        self.__zoom_out_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('zoom-out'),
            "Zoom Out",
            self, triggered=self.onZoomOut)

        self.__stats_menu = QtWidgets.QMenu()
        self.__stats_menu.aboutToShow.connect(self.onUpdateStatsMenu)

        self.__add_stat_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('list-add'),
            "Add stat",
            self)
        self.__add_stat_action.setMenu(self.__stats_menu)

        self.__toolbar = QtWidgets.QToolBar()
        self.__toolbar.addAction(self.__pause_action)
        self.__toolbar.addAction(self.__zoom_in_action)
        self.__toolbar.addAction(self.__zoom_out_action)
        self.__toolbar.addAction(self.__add_stat_action)
        self.addToolBar(Qt.TopToolBarArea, self.__toolbar)

        self.__stat_graphs = []

        self.__stat_list_layout = QtWidgets.QVBoxLayout()
        self.__stat_list_layout.setSpacing(4)

        self.__stat_list = QtWidgets.QWidget(self)
        self.__stat_list.setLayout(self.__stat_list_layout)

        self.__scroll_area = QtWidgets.QScrollArea(self)
        self.__scroll_area.setWidget(self.__stat_list)
        self.__scroll_area.setWidgetResizable(True)
        self.__scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setCentralWidget(self.__scroll_area)

        self.setVisible(
            int(self.app.settings.value(
                'dialog/stat_monitor/visible', False)))
        self.restoreGeometry(
            self.app.settings.value(
                'dialog/stat_monitor/geometry', b''))

    def storeState(self):
        s = self.app.settings
        s.beginGroup('dialog/stat_monitor')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.endGroup()

    def showEvent(self, event):
        self.visibilityChanged.emit(True)
        self.__update_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.__update_timer.stop()
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def onToggleRealtime(self):
        if self.__realtime:
            self.__realtime = False
            self.__pause_action.setIcon(
                QtGui.QIcon.fromTheme('media-playback-start'))
        else:
            self.__realtime = True
            self.__pause_action.setIcon(
                QtGui.QIcon.fromTheme('media-playback-pause'))

    def onZoomIn(self):
        self.__time_scale *= 2

    def onZoomOut(self):
        if self.time_scale > 1:
            self.__time_scale //= 2

    def onUpdate(self):
        expressions = {
            graph.id(): graph.expression()
            for graph in self.__stat_graphs}
        self.call_async(
            self.app.process.manager.call('STATS_FETCH', expressions),
            callback=self.onStatsFetched)

    def onStatsFetched(self, result):
        for graph in self.__stat_graphs:
            graph.setTimeseriesSet(result.get(graph.id(), None))

    def onUpdateStatsMenu(self):
        self.__stats_menu.clear()
        self.call_async(self.updateStatsMenuAsync())

    async def updateStatsMenuAsync(self):
        stat_list = await self.app.process.manager.call(
            'STATS_LIST')
        for name in stat_list:
            action = self.__stats_menu.addAction(str(name))
            action.triggered.connect(functools.partial(self.onAddStat, name))

    def onAddStat(self, name):
        graph = StatGraph(parent=self.__stat_list, name=name)
        self.__stat_graphs.append(graph)
        self.__stat_list_layout.addWidget(graph)
