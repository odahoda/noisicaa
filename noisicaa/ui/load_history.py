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

# mypy: loose

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets, QtGui


class LoadHistoryWidget(QtWidgets.QWidget):
    def __init__(self, width, height):
        super().__init__()

        self._width = width
        self._height = height
        self.setFixedSize(self._width, self._height)

        self._pixmap = QtGui.QPixmap(self._width, self._height)
        self._pixmap.fill(Qt.black)

        self._latest_value = None

        self._font = QtGui.QFont("Helvetica")
        self._font.setPixelSize(12)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        if self._latest_value is not None:
            painter.setPen(Qt.white)
            painter.setFont(self._font)
            painter.drawText(
                4, 1, self._width - 4, self._height - 1,
                Qt.AlignTop,
                "%d%%" % (100 * self._latest_value))

        return super().paintEvent(event)

    def addValue(self, value):
        value = max(0, min(value, 1))
        vh = int(self._height * value)

        self._pixmap.scroll(-2, 0, 0, 0, self._width, self._height)
        painter = QtGui.QPainter(self._pixmap)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        painter.drawRect(self._width - 2, 0, 2, self._height)
        painter.setBrush(QtGui.QColor(int(255 * value), 255 - int(255 * value), 0))
        painter.drawRect(self._width - 2, self._height - vh, 2, vh)

        self._latest_value = value

        self.update()
