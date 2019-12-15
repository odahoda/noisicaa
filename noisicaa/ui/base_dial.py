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
from typing import Optional, Callable, TypeVar

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import slots
from .qtyping import QGeneric

logger = logging.getLogger(__name__)


class RenderContext(object):
    def __init__(self, dial: 'BaseDial', painter: QtGui.QPainter) -> None:
        self.painter = painter

        self.value = dial.normalizedValue()

        self.size = min(dial.width(), dial.height())

        self.arc_width = int(max(6, min(self.size / 6, 20)))
        self.arc_size = int(self.size - self.arc_width - 2)

        if dial.isEnabled():
            self.arc_bg_color = QtGui.QColor(0, 0, 0)
            self.arc_fg_color = QtGui.QColor(100, 100, 255)
            self.knob_inner_color = QtGui.QColor(0, 0, 0)
            self.knob_border_color = QtGui.QColor(255, 255, 255)
            self.text_color = QtGui.QColor(0, 0, 0)
            self.dot_pen = QtGui.QPen(QtGui.QColor(160, 160, 160))
            self.dot_pen.setWidth(2)

        else:
            self.arc_bg_color = QtGui.QColor(80, 80, 80)
            self.arc_fg_color = QtGui.QColor(120, 120, 120)
            self.knob_inner_color = QtGui.QColor(80, 80, 80)
            self.knob_border_color = QtGui.QColor(140, 140, 140)
            self.text_color = QtGui.QColor(80, 80, 80)
            self.dot_pen = QtGui.QPen(QtGui.QColor(100, 100, 100))
            self.dot_pen.setWidth(2)


T = TypeVar('T')

class BaseDial(QGeneric[T], slots.SlotContainer, QtWidgets.QWidget):
    readOnly, setReadOnly, readOnlyChanged = slots.slot(bool, 'readOnly', default=False)
    # This class should also have slots 'value', 'default', 'minimum' and 'maximum', all of type
    # T. But Qt signals have to be created with a real type, they don't work with a TypeVar. So
    # those slots are added in subclasses with the concrete type of T. But every use of these slots
    # here results in a mypy error, which has been disabled with a 'type: ignore'.

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.__display_func = lambda value: '%s' % value

        self.readOnlyChanged.connect(lambda _: self.update())

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(50, 50)

    def minimumSizeHint(self) -> QtCore.QSize:
        min_size = self.minimumSize()
        if not min_size.isValid():
            min_size = QtCore.QSize(32, 32)
        return min_size

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return w

    def setDisplayFunc(self, func: Callable[[T], str]) -> None:
        self.__display_func = func
        self.update()

    def setRange(self, minimum: T, maximum: T) -> None:
        self.setMinimum(minimum)  # type: ignore
        self.setMaximum(maximum)  # type: ignore

    def normalizedValue(self) -> float:
        return self.normalize(self.value())  # type: ignore

    def normalize(self, value: T) -> float:
        raise NotImplementedError

    def denormalize(self, value: float) -> T:
        raise NotImplementedError

    def _render(self, ctxt: RenderContext) -> None:
        raise NotImplementedError

    def _renderArc(self, ctxt: RenderContext) -> None:
        pen = QtGui.QPen()
        pen.setColor(ctxt.arc_bg_color)
        pen.setWidth(ctxt.arc_width)
        pen.setCapStyle(Qt.RoundCap)
        ctxt.painter.setPen(pen)
        ctxt.painter.drawArc(
            -int(ctxt.arc_size / 2), -int(ctxt.arc_size / 2), ctxt.arc_size, ctxt.arc_size,
            225 * 16, -270 * 16)

    def _renderTrail(self, ctxt: RenderContext, zero_value: float) -> None:
        pen = QtGui.QPen()
        pen.setColor(ctxt.arc_fg_color)
        pen.setWidth(ctxt.arc_width - 2)
        pen.setCapStyle(Qt.RoundCap)
        ctxt.painter.setPen(pen)
        ctxt.painter.drawArc(
            -int(ctxt.arc_size / 2), -int(ctxt.arc_size / 2), ctxt.arc_size, ctxt.arc_size,
            225 * 16 - int(zero_value * 270 * 16), -int((ctxt.value - zero_value) * 270 * 16))

    def _renderKnob(self, ctxt: RenderContext) -> None:
        knob_pos = QtCore.QPointF(
            0.5 * ctxt.arc_size * math.cos(1.5 * math.pi * ctxt.value - 1.25 * math.pi),
            0.5 * ctxt.arc_size * math.sin(1.5 * math.pi * ctxt.value - 1.25 * math.pi))
        ctxt.painter.setPen(Qt.NoPen)
        ctxt.painter.setBrush(ctxt.knob_border_color)
        ctxt.painter.drawEllipse(knob_pos, ctxt.arc_width / 2 + 1, ctxt.arc_width / 2 + 1)
        ctxt.painter.setBrush(ctxt.knob_inner_color)
        ctxt.painter.drawEllipse(knob_pos, ctxt.arc_width / 2 - 1, ctxt.arc_width / 2 - 1)

    def _renderLabel(self, ctxt: RenderContext) -> None:
        if ctxt.size > 40:
            text = self.__display_func(self.value())  # type: ignore
            if text:
                font = QtGui.QFont("Arial")
                font.setPixelSize(10)
                ctxt.painter.setFont(font)
                pen = QtGui.QPen()
                pen.setColor(ctxt.text_color)
                ctxt.painter.setPen(pen)
                ctxt.painter.drawText(
                    QtCore.QRectF(
                        -ctxt.arc_size / 2, -ctxt.arc_size / 4,
                        ctxt.arc_size, ctxt.arc_size / 2),
                    Qt.AlignCenter,
                    text)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            ctxt = RenderContext(self, painter)

            painter.setRenderHints(
                QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

            painter.translate(self.width() / 2, self.height() / 2)

            self._render(ctxt)

        finally:
            painter.end()

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and not self.readOnly():
            self.setValue(self.default())  # type: ignore
