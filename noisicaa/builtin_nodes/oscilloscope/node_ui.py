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
from typing import Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui.graph import base_node
from . import model

logger = logging.getLogger(__name__)


class Oscilloscope(QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setMinimumSize(60, 60)

        self.__signal = []  # type: List[float]
        self.__insert_pos = 0

        self.__bg_color = QtGui.QColor(0, 0, 0)
        self.__border_color = QtGui.QColor(100, 200, 100)
        self.__grid_color = QtGui.QColor(40, 60, 40)
        self.__center_color = QtGui.QColor(60, 100, 60)
        self.__plot_pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
        self.__plot_pen.setWidth(2)

        self.__update_timer = QtCore.QTimer(self)
        self.__update_timer.timeout.connect(lambda: self.update())
        self.__update_timer.setInterval(1000 // 20)

    def addValue(self, value: float) -> None:
        if not self.__signal:
            return

        if self.__insert_pos >= len(self.__signal):
            self.__insert_pos = 0

        self.__signal[self.__insert_pos] = value
        self.__insert_pos += 1

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(100, 100)

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        self.__update_timer.start()
        super().showEvent(evt)

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        self.__update_timer.stop()
        super().hideEvent(evt)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        if evt.size().width() > len(self.__signal):
            self.__signal = [0.0] * evt.size().width()

        elif evt.size().width() < len(self.__signal):
            del self.__signal[:len(self.__signal) - evt.size().width()]

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        assert len(self.__signal) == self.size().width()

        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self.__bg_color)

            w = self.width() - 10
            h = self.height() - 10

            for g in (1, 2, 3, 4, 6, 7, 8, 9, 5, 0, 10):
                if g in (0, 10):
                    color = self.__border_color
                elif g == 5:
                    color = self.__center_color
                else:
                    color = self.__grid_color

                painter.fillRect(int(g * (w - 1) / 10) + 5, 5, 1, h, color)
                painter.fillRect(5, int(g * (h - 1) / 10) + 5, w, 1, color)

            painter.setPen(self.__plot_pen)
            for x, value in enumerate(self.__signal, 5):
                y = h - int((h - 1) * (value + 1.0) / 2.0) + 5
                painter.drawPoint(x, y)

        finally:
            painter.end()


class OscilloscopeNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: model.Oscilloscope, session_prefix: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.__plot = Oscilloscope()

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__plot)
        self.setLayout(l1)


    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        signal_uri = 'http://noisicaa.odahoda.de/lv2/processor_oscilloscope#signal'
        if signal_uri in msg:
            signal = msg[signal_uri]
            for value in signal:
                self.__plot.addValue(value)


class OscilloscopeNode(base_node.Node):
    has_window = True

    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.Oscilloscope), type(node).__name__
        self.__widget = None  # type: QtWidgets.QWidget
        self.__node = node  # type: model.Oscilloscope

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None

        body = OscilloscopeNodeWidget(
            node=self.__node,
            session_prefix='inline',
            context=self.context)
        self.add_cleanup_function(body.cleanup)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__widget = QtWidgets.QScrollArea()
        self.__widget.setWidgetResizable(True)
        self.__widget.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.__widget.setWidget(body)

        return self.__widget

    def createWindow(self, **kwargs: Any) -> QtWidgets.QWidget:
        window = QtWidgets.QDialog(**kwargs)
        window.setAttribute(Qt.WA_DeleteOnClose, False)
        window.setWindowTitle("Oscilloscope")

        body = OscilloscopeNodeWidget(
            node=self.__node,
            session_prefix='window',
            context=self.context)
        self.add_cleanup_function(body.cleanup)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(body)
        window.setLayout(layout)

        return window
