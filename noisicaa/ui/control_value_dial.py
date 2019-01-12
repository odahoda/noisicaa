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
from typing import Optional, Callable

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import slots

logger = logging.getLogger(__name__)


class ControlValueDial(slots.SlotContainer, QtWidgets.QWidget):
    value, setValue, valueChanged = slots.slot(float, 'value', default=0.0)
    default, setDefault, defaultChanged = slots.slot(float, 'default', default=0.0)
    logScale, setLogScale, logScaleChanged = slots.slot(bool, 'logScale', default=False)
    minimum, setMinimum, minimumChanged = slots.slot(float, 'minimum', default=-1.0)
    maximum, setMaximum, maximumChanged = slots.slot(float, 'maximum', default=1.0)

    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent=parent)

        self.valueChanged.connect(lambda _: self.update())
        self.maximumChanged.connect(lambda _: self.update())
        self.minimumChanged.connect(lambda _: self.update())

        self.__display_func = lambda value: '%.2f' % value

        self.__dragging = False
        self.__drag_pos = None  # type: QtCore.QPoint

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(50, 50)

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(32, 32)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return w

    def setRange(self, minimum: float, maximum: float) -> None:
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def setDisplayFunc(self, func: Callable[[float], str]) -> None:
        self.__display_func = func
        self.update()

    def normalizedValue(self) -> float:
        return self.normalize(self.value())

    def normalize(self, value: float) -> float:
        value = max(self.minimum(), min(value, self.maximum()))
        if self.logScale():
            return (
                math.log(value - self.minimum() + 1)
                / math.log(self.maximum() - self.minimum() + 1))
        else:
            return (value - self.minimum()) / (self.maximum() - self.minimum())

    def denormalize(self, value: float) -> float:
        value = max(0.0, min(value, 1.0))
        if self.logScale():
            return (
                pow(math.e, value * math.log(self.maximum() - self.minimum() + 1))
                + self.minimum() - 1)
        else:
            return (self.maximum() - self.minimum()) * value + self.minimum()

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        value = self.normalizedValue()

        size = min(self.width(), self.height())

        arc_width = int(max(6, min(size / 6, 20)))
        arc_size = int(size - arc_width - 2)

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHints(
                QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

            painter.translate(self.width() / 2, self.height() / 2)

            pen = QtGui.QPen()
            pen.setColor(Qt.black)
            pen.setWidth(arc_width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                -int(arc_size / 2), -int(arc_size / 2), arc_size, arc_size,
                225 * 16, -270 * 16)

            zero_value = self.normalize(0.0)
            pen = QtGui.QPen()
            pen.setColor(QtGui.QColor(100, 100, 255))
            pen.setWidth(arc_width - 2)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                -int(arc_size / 2), -int(arc_size / 2), arc_size, arc_size,
                225 * 16 - int(zero_value * 270 * 16), -int((value - zero_value) * 270 * 16))

            knob_pos = QtCore.QPointF(
                0.5 * arc_size * math.cos(1.5 * math.pi * value - 1.25 * math.pi),
                0.5 * arc_size * math.sin(1.5 * math.pi * value - 1.25 * math.pi))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(255, 255, 255))
            painter.drawEllipse(knob_pos, arc_width / 2 + 1, arc_width / 2 + 1)
            painter.setBrush(Qt.black)
            painter.drawEllipse(knob_pos, arc_width / 2 - 1, arc_width / 2 - 1)

            if size > 40:
                font = QtGui.QFont("Arial")
                font.setPixelSize(10)
                painter.setFont(font)
                pen = QtGui.QPen()
                pen.setColor(Qt.black)
                painter.setPen(pen)
                painter.drawText(
                    QtCore.QRectF(-arc_size / 2, -arc_size / 4, arc_size, arc_size / 2),
                    Qt.AlignCenter,
                    self.__display_func(self.value()))

        finally:
            painter.end()

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.setValue(self.default())

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
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

    def mouseReleasevent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging and evt.button() == Qt.LeftButton:
            self.__dragging = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)
