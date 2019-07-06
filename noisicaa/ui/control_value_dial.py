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

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import slots
from . import base_dial

logger = logging.getLogger(__name__)


class ControlValueDial(base_dial.BaseDial):
    value, setValue, valueChanged = slots.slot(float, 'value', default=0.0)
    default, setDefault, defaultChanged = slots.slot(float, 'default', default=0.0)
    logScale, setLogScale, logScaleChanged = slots.slot(bool, 'logScale', default=False)
    minimum, setMinimum, minimumChanged = slots.slot(float, 'minimum', default=-1.0)
    maximum, setMaximum, maximumChanged = slots.slot(float, 'maximum', default=1.0)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.valueChanged.connect(lambda _: self.update())
        self.maximumChanged.connect(lambda _: self.update())
        self.minimumChanged.connect(lambda _: self.update())
        self.logScaleChanged.connect(lambda _: self.update())

        self.setDisplayFunc(lambda value: '%.2f' % value)

        self.__dragging = False
        self.__drag_pos = None  # type: QtCore.QPoint

    def normalize(self, value: float) -> float:
        try:
            value = max(self.minimum(), min(value, self.maximum()))
            if self.logScale():
                return (
                    math.log(value - self.minimum() + 1)
                    / math.log(self.maximum() - self.minimum() + 1))
            else:
                return (value - self.minimum()) / (self.maximum() - self.minimum())
        except ArithmeticError:
            return self.minimum()

    def denormalize(self, value: float) -> float:
        try:
            value = max(0.0, min(value, 1.0))
            if self.logScale():
                return (
                    pow(math.e, value * math.log(self.maximum() - self.minimum() + 1))
                    + self.minimum() - 1)
            else:
                return (self.maximum() - self.minimum()) * value + self.minimum()
        except ArithmeticError:
            return self.minimum()

    def _render(self, ctxt: base_dial.RenderContext) -> None:
        self._renderArc(ctxt)
        self._renderTrail(ctxt, self.normalize(0.0))
        self._renderKnob(ctxt)
        self._renderLabel(ctxt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and not self.readOnly():
            self.__dragging = True
            self.__drag_pos = self.mapToGlobal(evt.pos())
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging:
            delta = (self.mapToGlobal(evt.pos()) - self.__drag_pos).x()
            self.__drag_pos = self.mapToGlobal(evt.pos())

            step_size = 0.005
            if evt.modifiers() & Qt.ShiftModifier:
                step_size /= 10

            value = self.denormalize(self.normalizedValue() + delta * step_size)
            value = max(self.minimum(), min(value, self.maximum()))
            self.setValue(value)

            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging and evt.button() == Qt.LeftButton:
            self.__dragging = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)
