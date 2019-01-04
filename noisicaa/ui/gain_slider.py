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
from typing import Optional, Callable

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.ui import slots

logger = logging.getLogger(__name__)


class GainSlider(slots.SlotContainer, QtWidgets.QWidget):
    orientation, setOrientation, orientationChanged = slots.slot(
        Qt.Orientation, 'orientation', default=Qt.Horizontal)
    value, setValue, valueChanged = slots.slot(float, 'value', default=0.0)
    default, setDefault, defaultChanged = slots.slot(float, 'default', default=0.0)
    minimum, setMinimum, minimumChanged = slots.slot(float, 'minimum', default=-20.0)
    maximum, setMaximum, maximumChanged = slots.slot(float, 'maximum', default=20.0)

    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent=parent)

        self.orientationChanged.connect(lambda _: self.update())
        self.valueChanged.connect(lambda _: self.update())
        self.maximumChanged.connect(lambda _: self.update())
        self.minimumChanged.connect(lambda _: self.update())

        self.__display_func = lambda value: '%.2f' % value

        self.__dragging = False
        self.__drag_pos = None  # type: QtCore.QPoint

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(50, 50)

    def minimumSizeHint(self) -> QtCore.QSize:
        if self.orientation() == Qt.Horizontal:
            return QtCore.QSize(100, 24)
        else:
            return QtCore.QSize(24, 100)

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
        return (value - self.minimum()) / (self.maximum() - self.minimum())

    def denormalize(self, value: float) -> float:
        value = max(0.0, min(value, 1.0))
        return (self.maximum() - self.minimum()) * value + self.minimum()

    def normalizedValueToOffset(self, value: float) -> int:
        if self.orientation() == Qt.Horizontal:
            return int((self.width() - 5) * value)
        else:
            return int((self.height() - 5) * value)

    def valueToOffset(self, value: float) -> int:
        if self.orientation() == Qt.Horizontal:
            return int((self.width() - 5) * self.normalize(value))
        else:
            return int((self.height() - 5) * self.normalize(value))

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        w, h = self.width(), self.height()
        value = self.normalizedValue()

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHints(
                QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

            painter.fillRect(0, 0, w, h, Qt.black)

            if self.orientation() == Qt.Horizontal:
                show_ticks = (w > 200) and (h > 20)

                if show_ticks:
                    m = self.minimum()
                    while m <= self.maximum():
                        x = self.valueToOffset(m)
                        painter.fillRect(x + 2, 2, 1, h - 4, QtGui.QColor(60, 60, 60))
                        m += 5.0

                x = self.normalizedValueToOffset(value)
                painter.fillRect(2, 2, x, h - 4, QtGui.QColor(100, 100, 255))
                painter.fillRect(x + 2, 2, 1, h - 4, QtGui.QColor(255, 100, 100))

                if show_ticks:
                    m = self.minimum()
                    while m <= self.maximum():
                        x = self.valueToOffset(m)
                        painter.fillRect(x + 2, 2, 1, 4, QtGui.QColor(255, 255, 255))
                        painter.fillRect(x + 2, h - 6, 1, 4, QtGui.QColor(255, 255, 255))
                        m += 5.0

            else:
                show_ticks = (h > 200) and (w > 20)

                if show_ticks:
                    m = self.minimum()
                    while m <= self.maximum():
                        y = self.valueToOffset(m)
                        painter.fillRect(2, h - y - 3, w - 4, 1, QtGui.QColor(60, 60, 60))
                        m += 5.0

                y = self.normalizedValueToOffset(value)
                painter.fillRect(2, h - y - 2, w - 4, y, QtGui.QColor(100, 100, 255))
                painter.fillRect(2, h - y - 3, w - 4, 1, QtGui.QColor(255, 100, 100))

                if show_ticks:
                    m = self.minimum()
                    while m <= self.maximum():
                        y = self.valueToOffset(m)
                        painter.fillRect(2, h - y - 3, 4, 1, QtGui.QColor(255, 255, 255))
                        painter.fillRect(w - 6, h - y - 3, 4, 1, QtGui.QColor(255, 255, 255))
                        m += 5.0

            if w > 60 and h > 14:
                font = QtGui.QFont("Arial")
                font.setPixelSize(12)
                painter.setFont(font)

                label = self.__display_func(self.value())
                fm = QtGui.QFontMetrics(font)
                r = fm.boundingRect(label)
                r.moveTopLeft(QtCore.QPoint(
                    int((w - r.width()) / 2 + r.left()),
                    int((h - r.height()) / 2 + 1.5 * fm.capHeight())))

                pen = QtGui.QPen()
                pen.setColor(Qt.black)
                painter.setPen(pen)
                for x, y, in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    painter.drawText(r.topLeft() + QtCore.QPoint(x, y), label)

                pen = QtGui.QPen()
                pen.setColor(Qt.white)
                painter.setPen(pen)
                painter.drawText(r.topLeft(), label)

        finally:
            painter.end()

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.setValue(self.default())

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.__dragging = True
            self.__drag_pos = self.mapToGlobal(evt.pos())

            if not evt.modifiers() & Qt.ShiftModifier:
                if self.orientation() == Qt.Horizontal:
                    self.setValue(self.denormalize((evt.pos().x() - 2) / (self.width() - 5)))
                else:
                    self.setValue(self.denormalize(1.0 - (evt.pos().y() - 2) / (self.height() - 5)))

            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging:
            delta_p = (self.mapToGlobal(evt.pos()) - self.__drag_pos)
            self.__drag_pos = self.mapToGlobal(evt.pos())

            if evt.modifiers() & Qt.ShiftModifier:
                if self.orientation() == Qt.Horizontal:
                    delta = delta_p.x()
                else:
                    delta = -delta_p.y()

                step_size = 0.0001
                value = self.denormalize(self.normalizedValue() + delta * step_size)
                value = max(self.minimum(), min(value, self.maximum()))
                self.setValue(value)

            else:
                if self.orientation() == Qt.Horizontal:
                    self.setValue(self.denormalize((evt.pos().x() - 2) / (self.width() - 5)))
                else:
                    self.setValue(self.denormalize(1.0 - (evt.pos().y() - 2) / (self.height() - 5)))

            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleasevent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__dragging and evt.button() == Qt.LeftButton:
            self.__dragging = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)
