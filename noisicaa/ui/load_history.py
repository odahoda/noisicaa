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

# mypy: loose

import math
from typing import List

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets, QtGui


class LoadHistoryWidget(QtWidgets.QWidget):
    def __init__(self, width, height):
        super().__init__()

        self.__width = width
        self.__height = height
        self.setFixedSize(self.__width, self.__height)

        self.__pixmap = QtGui.QPixmap(self.__width, self.__height)
        self.__pixmap.fill(Qt.black)

        self.__history = []  # type: List[float]

        self.__font = QtGui.QFont("Helvetica")
        self.__font.setPixelSize(12)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self.__pixmap)

        if len(self.__history) > 5:
            avg = sum(self.__history) / len(self.__history)
            stddev = math.sqrt(sum((v - avg) ** 2 for v in self.__history) / len(self.__history))

            painter.setPen(Qt.white)
            painter.setFont(self.__font)
            painter.drawText(
                4, 1, self.__width - 4, self.__height - 1,
                Qt.AlignTop,
                "%d\u00b1%d%%" % (avg, stddev))

        return super().paintEvent(event)

    def addValue(self, value):
        value = max(0, min(value, 1))
        vh = int(self.__height * value)

        self.__pixmap.scroll(-2, 0, 0, 0, self.__width, self.__height)
        painter = QtGui.QPainter(self.__pixmap)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        painter.drawRect(self.__width - 2, 0, 2, self.__height)
        painter.setBrush(QtGui.QColor(int(255 * value), 255 - int(255 * value), 0))
        painter.drawRect(self.__width - 2, self.__height - vh, 2, vh)

        self.__history.append(100 * value)
        if len(self.__history) > 50:
            del self.__history[:-50]

        self.update()
