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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import vumeter
from noisicaa.ui.graph import base_node

logger = logging.getLogger(__name__)


class VUMeterNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: music.BaseNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__vu_meter = vumeter.VUMeter(self)

        self.__meter_urid = self.app.urid_mapper.map(
            'http://noisicaa.odahoda.de/lv2/processor_vumeter#meter')

        listener = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)
        self.add_cleanup_function(listener.remove)

        self.setMinimumSize(QtCore.QSize(10, 10))

        self.__current_orientation = None  # type: Qt.Orientation

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__vu_meter)
        self.setLayout(layout)

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        meter = 'http://noisicaa.odahoda.de/lv2/processor_vumeter#meter'
        if meter in msg:
            current_left, peak_left, current_right, peak_right = msg[meter]
            self.__vu_meter.setLeftValue(current_left)
            self.__vu_meter.setLeftPeak(peak_left)
            self.__vu_meter.setRightValue(current_right)
            self.__vu_meter.setRightPeak(peak_right)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        w, h = self.width(), self.height()
        if w > h:
            orientation = Qt.Horizontal
        else:
            orientation = Qt.Vertical

        if orientation == self.__current_orientation:
            return

        self.__vu_meter.setOrientation(orientation)

        self.__current_orientation = orientation


class VUMeterNode(base_node.Node):
    def createBodyWidget(self) -> QtWidgets.QWidget:
        widget = VUMeterNodeWidget(node=self.node(), context=self.context)
        self.add_cleanup_function(widget.cleanup)
        return widget
