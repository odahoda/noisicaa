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
import math
from typing import Optional

from PySide2.QtCore import Qt
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

from . import slots
from . import base_dial

logger = logging.getLogger(__name__)


class IntDial(base_dial.BaseDial):
    value, setValue, valueChanged = slots.slot(int, 'value', default=0)
    default, setDefault, defaultChanged = slots.slot(int, 'default', default=0)
    minimum, setMinimum, minimumChanged = slots.slot(int, 'minimum', default=0)
    maximum, setMaximum, maximumChanged = slots.slot(int, 'maximum', default=10)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.valueChanged.connect(lambda _: self.update())
        self.maximumChanged.connect(lambda _: self.update())
        self.minimumChanged.connect(lambda _: self.update())

        self.setDisplayFunc(lambda value: '%d' % value)

        self.__dragging = False
        self.__drag_pos = None  # type: QtCore.QPoint
        self.__drag_start_value = None  # type: int

    def normalize(self, value: base_dial.T) -> float:
        try:
            value = max(self.minimum(), min(value, self.maximum()))
            return (value - self.minimum()) / (self.maximum() - self.minimum())
        except ArithmeticError:
            return 0.0

    def denormalize(self, value: float) -> int:
        return round((self.maximum() - self.minimum()) * value + self.minimum())

    def _render(self, ctxt: base_dial.RenderContext) -> None:
        self._renderArc(ctxt)
        self._renderTrail(ctxt, self.normalize(0))

        for v in range(self.minimum(), self.maximum() + 1):
            nv = self.normalize(v)
            v_pos = QtCore.QPointF(
                0.5 * ctxt.arc_size * math.cos(1.5 * math.pi * nv - 1.25 * math.pi),
                0.5 * ctxt.arc_size * math.sin(1.5 * math.pi * nv - 1.25 * math.pi))
            ctxt.painter.setPen(ctxt.dot_pen)
            ctxt.painter.drawPoint(v_pos)

        self._renderKnob(ctxt)
        self._renderLabel(ctxt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and not self.readOnly():
            self.__dragging = True
            self.__drag_pos = self.mapToGlobal(evt.pos())
            self.__drag_start_value = self.value()
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging:
            delta = (self.mapToGlobal(evt.pos()) - self.__drag_pos).x()

            value = self.__drag_start_value + delta // 20
            value = max(self.minimum(), min(value, self.maximum()))
            self.setValue(value)

            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleasEevent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging and evt.button() == Qt.LeftButton:
            self.__dragging = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)
