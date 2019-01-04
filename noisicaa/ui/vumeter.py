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
import math
from typing import Optional, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.ui import slots

logger = logging.getLogger(__name__)


class VUMeter(slots.SlotContainer, QtWidgets.QWidget):
    orientation, setOrientation, orientationChanged = slots.slot(
        Qt.Orientation, 'orientation', default=Qt.Horizontal)
    minimum, setMinimum, minimumChanged = slots.slot(float, 'minimum', default=-52.0)
    maximum, setMaximum, maximumChanged = slots.slot(float, 'maximum', default=22.0)
    leftValue, setLeftValue, leftValueChanged = slots.slot(float, 'leftValue', default=-50.0)
    leftPeak, setLeftPeak, leftPeakChanged = slots.slot(float, 'leftPeak', default=-50.0)
    rightValue, setRightValue, rightValueChanged = slots.slot(float, 'rightValue', default=-50.0)
    rightPeak, setRightPeak, rightPeakChanged = slots.slot(float, 'rightPeak', default=-50.0)

    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent=parent)

        self.minimumChanged.connect(lambda _: self.update())
        self.maximumChanged.connect(lambda _: self.update())
        self.leftValueChanged.connect(lambda _: self.update())
        self.leftPeakChanged.connect(lambda _: self.update())
        self.rightValueChanged.connect(lambda _: self.update())
        self.rightPeakChanged.connect(lambda _: self.update())
        self.orientationChanged.connect(lambda _: self.update())

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(20, 20)

    def normalizeValue(self, value: float) -> float:
        value = max(self.minimum(), min(value, self.maximum()))
        value = (value - self.minimum()) / (self.maximum() - self.minimum())
        return value

    def __drawHBar(
            self, painter: QtGui.QPainter, rect: QtCore.QRect,
            value: float, peak: float, ticks: List[Tuple[float, str]]
        ) -> None:
        value = self.normalizeValue(value)
        peak = self.normalizeValue(peak)

        x, y = rect.left(), rect.top()
        w, h = rect.width(), rect.height()

        if value > 0.0:
            value_x = int(w * value)
            warn_x = int(w * self.normalizeValue(-9.0))
            clip_x = int(w * self.normalizeValue(0.0))

            painter.fillRect(
                QtCore.QRect(x, y, min(value_x, warn_x), h),
                Qt.green)
            if value_x > warn_x:
                painter.fillRect(
                    QtCore.QRect(x + warn_x, y, min(value_x, clip_x) - warn_x, h),
                    Qt.yellow)
            if value_x > clip_x:
                painter.fillRect(
                    QtCore.QRect(x + clip_x, y, value_x - clip_x, h),
                    Qt.red)

        if peak > 0.0:
            peak_x = int((w - 1) * peak)
            painter.fillRect(QtCore.QRect(x + peak_x - 1, y, 2, h), Qt.red)

        tick_h = int(h / 5)
        for tick, _ in ticks:
            tick_x = int(w * self.normalizeValue(tick))
            painter.fillRect(QtCore.QRect(x + tick_x, y, 1, tick_h), Qt.white)
            painter.fillRect(QtCore.QRect(x + tick_x, y + h - tick_h, 1, tick_h), Qt.white)

    def __drawVBar(
            self, painter: QtGui.QPainter, rect: QtCore.QRect,
            value: float, peak: float, ticks: List[Tuple[float, str]]
        ) -> None:
        value = self.normalizeValue(value)
        peak = self.normalizeValue(peak)

        x, y = rect.left(), rect.top()
        w, h = rect.width(), rect.height()

        if value > 0.0:
            value_y = int(h * value)
            warn_y = int(h * self.normalizeValue(-9.0))
            clip_y = int(h * self.normalizeValue(0.0))

            painter.fillRect(
                QtCore.QRect(x, y + h - min(value_y, warn_y), w, min(value_y, warn_y)),
                Qt.green)
            if value_y > warn_y:
                painter.fillRect(
                    QtCore.QRect(x, y + h - min(value_y, clip_y), w, min(value_y, clip_y) - warn_y),
                    Qt.yellow)
            if value_y > clip_y:
                painter.fillRect(
                    QtCore.QRect(x, y + h - value_y, w, value_y - clip_y),
                    Qt.red)

        if peak > 0.0:
            peak_y = int(int((h - 1) * peak))
            painter.fillRect(QtCore.QRect(x, y + h - peak_y - 1, w, 2), Qt.red)

        tick_w = int(w / 5)
        for tick, _ in ticks:
            tick_y = int(h * self.normalizeValue(tick))
            painter.fillRect(QtCore.QRect(x, y + tick_y, tick_w, 1), Qt.white)
            painter.fillRect(QtCore.QRect(x + w - tick_w, y + tick_y, tick_w, 1), Qt.white)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        w, h = self.width(), self.height()

        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(0, 0, w, h, Qt.black)

            font = QtGui.QFont("Arial")
            font.setPixelSize(12)
            painter.setFont(font)
            fm = QtGui.QFontMetrics(font)

            ticks = []
            tick = math.modf(self.minimum() / 10.0)[1] * 10.0
            while tick <= self.maximum():
                label = '%+.0f' % tick
                if label == '+0':
                    label = '0dB'
                ticks.append((tick, label))
                tick += 10.0

            if self.orientation() == Qt.Horizontal:
                if h > 60:
                    label_h = max(14, min(h / 4, 30))
                    bar_h = int((h - 12 - label_h) / 2)
                else:
                    label_h = 0
                    bar_h = int((h - 6) / 2)

                label_top = int((h - 14) / 2)
                label_bottom = label_top + 14

                for tick, label in ticks:
                    tick_x = int((w - 4) * self.normalizeValue(tick))
                    painter.fillRect(
                        2 + tick_x, 2, 1, label_top - 2,
                        QtGui.QColor(60, 60, 60))
                    painter.fillRect(
                        2 + tick_x, 2 + label_bottom, 1, h - label_bottom - 4,
                        QtGui.QColor(60, 60, 60))

                    if label_h > 0:
                        pen = QtGui.QPen()
                        pen.setColor(Qt.white)
                        painter.setPen(pen)
                        r = fm.boundingRect(label)
                        painter.drawText(
                            QtCore.QPoint(
                                int(tick_x - r.width() / 2),
                                int((h - r.height()) / 2 + 1.5 * fm.capHeight())),
                            label)

                self.__drawHBar(
                    painter,
                    QtCore.QRect(2, 2, w - 4, bar_h),
                    self.leftValue(), self.leftPeak(), ticks)
                self.__drawHBar(
                    painter,
                    QtCore.QRect(2, h - bar_h - 2, w - 4, bar_h),
                    self.rightValue(), self.rightPeak(), ticks)
            else:
                if w > 80:
                    label_w = max(30, min(w / 3, 50))
                    bar_w = int((w - 12 - label_w) / 2)
                else:
                    label_w = 0
                    bar_w = int((w - 6) / 2)

                label_left = int((w - 30) / 2)
                label_right = label_left + 30

                for tick, label in ticks:
                    tick_y = h - 2 - int((h - 4) * self.normalizeValue(tick))
                    painter.fillRect(
                        2, tick_y, label_left - 2, 1,
                        QtGui.QColor(60, 60, 60))
                    painter.fillRect(
                        2 + label_right, tick_y, w - label_right - 4, 1,
                        QtGui.QColor(60, 60, 60))

                    if label_w > 0:
                        pen = QtGui.QPen()
                        pen.setColor(Qt.white)
                        painter.setPen(pen)
                        fm = QtGui.QFontMetrics(font)
                        r = fm.boundingRect(label)
                        painter.drawText(
                            QtCore.QPoint(
                                int((w - r.width()) / 2),
                                int(tick_y + 0.5 * fm.capHeight())),
                            label)

                self.__drawVBar(
                    painter,
                    QtCore.QRect(2, 2, bar_w, h - 4),
                    self.leftValue(), self.leftPeak(), ticks)
                self.__drawVBar(
                    painter,
                    QtCore.QRect(w - bar_w - 2, 2, bar_w, h - 4),
                    self.rightValue(), self.rightPeak(), ticks)

        finally:
            painter.end()
