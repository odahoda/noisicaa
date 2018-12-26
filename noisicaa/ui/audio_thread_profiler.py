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

import logging
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtSvg
from PyQt5 import QtWidgets

from . import ui_base


logger = logging.getLogger(__name__)


class AudioThreadProfiler(ui_base.CommonMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setWindowTitle("Audio Thread Profiler")
        self.setWindowFlags(Qt.Dialog)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.__duration = QtWidgets.QSpinBox()
        self.__duration.setSuffix("sec")
        self.__duration.setValue(30)
        self.__duration.setMinimum(1)
        self.__duration.setMaximum(1000)

        start = QtWidgets.QPushButton("Start")
        start.clicked.connect(lambda: self.call_async(self.startProfile()))

        icon_size = QtCore.QSize(32, 32)

        zoom_in_action = QtWidgets.QAction("Zoom in", self)
        zoom_in_action.setIcon(QtGui.QIcon.fromTheme('zoom-in'))
        zoom_in_action.triggered.connect(self.zoomIn)

        zoom_in_button = QtWidgets.QToolButton(self)
        zoom_in_button.setAutoRaise(True)
        zoom_in_button.setIconSize(icon_size)
        zoom_in_button.setDefaultAction(zoom_in_action)

        zoom_out_action = QtWidgets.QAction("Zoom out", self)
        zoom_out_action.setIcon(QtGui.QIcon.fromTheme('zoom-out'))
        zoom_out_action.triggered.connect(self.zoomOut)

        zoom_out_button = QtWidgets.QToolButton(self)
        zoom_out_button.setAutoRaise(True)
        zoom_out_button.setIconSize(icon_size)
        zoom_out_button.setDefaultAction(zoom_out_action)

        self.__item = None  # type: QtSvg.QGraphicsSvgItem

        self.__scene = QtWidgets.QGraphicsScene()

        self.__graph_display = QtWidgets.QGraphicsView()
        self.__graph_display.setScene(self.__scene)
        self.__graph_display.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.__graph_display.setMinimumSize(600, 600)

        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.addWidget(QtWidgets.QLabel("Duration: "))
        toolbar_layout.addWidget(self.__duration)
        toolbar_layout.addWidget(start)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(zoom_in_button)
        toolbar_layout.addWidget(zoom_out_button)
        toolbar_layout.addStretch(1)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.__graph_display, 1)
        self.setLayout(main_layout)

    async def startProfile(self) -> None:
        self.setEnabled(False)
        self.setCursor(Qt.BusyCursor)

        if self.__item is not None:
            self.__scene.removeItem(self.__item)
            self.__item = None

        try:
            svg = await self.audioproc_client.profile_audio_thread(
                duration=self.__duration.value())

            renderer = QtSvg.QSvgRenderer()
            renderer.load(svg)

            self.__item = QtSvg.QGraphicsSvgItem()
            self.__item.setSharedRenderer(renderer)
            self.__scene.addItem(self.__item)

        finally:
            self.setEnabled(True)
            self.unsetCursor()

    def zoomIn(self) -> None:
        self.__graph_display.scale(1.4, 1.4)

    def zoomOut(self) -> None:
        self.__graph_display.scale(1.0 / 1.4, 1.0 / 1.4)
