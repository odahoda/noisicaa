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

import fractions
import logging
import typing
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa.ui import slots
from noisicaa.ui import ui_base

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    QObjectMixin = QtCore.QObject
    QWidgetMixin = QtWidgets.QWidget
else:
    QObjectMixin = object
    QWidgetMixin = object


class ScaledTimeMixin(ui_base.ProjectMixin, QObjectMixin):
    scaleXChanged = QtCore.pyqtSignal(fractions.Fraction)
    contentWidthChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # pixels per beat
        self.__scale_x = fractions.Fraction(500, 1)
        self.__content_width = 100
        self.project.duration_changed.add(lambda _: self.__updateContentWidth())

        self.__updateContentWidth()

    def __updateContentWidth(self) -> None:
        width = int(self.project.duration.fraction * self.__scale_x) + 120
        self.setContentWidth(width)

    def leftMargin(self) -> int:
        return 100

    def projectEndTime(self) -> audioproc.MusicalTime:
        return audioproc.MusicalTime() + self.project.duration

    def contentWidth(self) -> int:
        return self.__content_width

    def setContentWidth(self, width: int) -> None:
        if width == self.__content_width:
            return

        self.__content_width = width
        self.contentWidthChanged.emit(self.__content_width)

    def scaleX(self) -> fractions.Fraction:
        return self.__scale_x

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.__updateContentWidth()
        self.scaleXChanged.emit(self.__scale_x)


class ContinuousTimeMixin(ScaledTimeMixin, slots.SlotContainer):
    additionalXOffset, setAdditionalXOffset, additionalXOffsetChanged = slots.slot(
        int, 'additionalXOffset', default=0)
    snapToGrid, setSnapToGrid, snapToGridChanged = slots.slot(bool, 'snapToGrid', default=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__grid_step = audioproc.MusicalDuration(1, 1)

        self.scaleXChanged.connect(self.__scaleXChanged)
        self.__scaleXChanged(self.scaleX())

    def __scaleXChanged(self, scale_x: fractions.Fraction) -> None:
        self.__grid_step = audioproc.MusicalDuration(1, 64)
        min_dist = 96
        while int(self.__grid_step * scale_x) <= min_dist:
            self.__grid_step *= 2
            if int(self.__grid_step) > 1:
                min_dist = 36

    def durationPerPixel(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1 / self.scaleX())

    def timeToX(self, time: audioproc.MusicalTime) -> int:
        return self.leftMargin() + self.additionalXOffset() + int(self.scaleX() * time.fraction)

    def xToTime(self, x: int) -> audioproc.MusicalTime:
        x -= self.leftMargin() + self.additionalXOffset()
        if x <= 0:
            return audioproc.MusicalTime(0, 1)

        return audioproc.MusicalTime(x / self.scaleX())

    def gridStep(self) -> audioproc.MusicalDuration:
        return self.__grid_step

    def shouldSnap(self, evt: QtGui.QMouseEvent) -> bool:
        return self.snapToGrid() and not evt.modifiers() & Qt.ShiftModifier

    def snapTime(self, time: audioproc.MusicalTime) -> audioproc.MusicalTime:
        grid_time = (
            audioproc.MusicalTime(0, 1)
            + self.gridStep() * int(round(float(time / self.gridStep()))))
        time_x = int(time * self.scaleX())
        grid_x = int(grid_time * self.scaleX())
        if abs(time_x - grid_x) <= 10:
            return grid_time
        return time

    def renderTimeGrid(
            self, painter: QtGui.QPainter, rect: QtCore.QRect, *, show_numbers: bool = False
    ) -> None:
        grid_step = self.gridStep()

        tick_num = int(self.xToTime(rect.x()) / grid_step)
        tick_time = (grid_step * tick_num).as_time()
        while tick_time < self.projectEndTime():
            x = self.timeToX(tick_time)
            if x > rect.right():
                break

            if tick_num == 0:
                painter.fillRect(x, rect.y(), 2, rect.height(), Qt.black)
            else:
                if tick_time % audioproc.MusicalTime(1, 1) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(0, 0, 0)
                elif tick_time % audioproc.MusicalTime(1, 4) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(160, 160, 160)
                elif tick_time % audioproc.MusicalTime(1, 8) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(185, 185, 185)
                elif tick_time % audioproc.MusicalTime(1, 16) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(210, 210, 210)
                elif tick_time % audioproc.MusicalTime(1, 32) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(225, 225, 225)
                else:
                    c = QtGui.QColor(240, 240, 240)

                painter.fillRect(x, rect.y(), 1, rect.height(), c)

            if (show_numbers
                    and tick_time % audioproc.MusicalTime(1, 1) == audioproc.MusicalTime(0, 1)):
                beat_num = int(tick_time / audioproc.MusicalTime(1, 4))
                painter.setPen(Qt.black)
                painter.drawText(x + 5, 12, '%d' % (beat_num + 1))

            tick_time += grid_step
            tick_num += 1

        x = self.timeToX(self.projectEndTime())
        painter.fillRect(x, rect.y(), 2, rect.height(), Qt.black)


class TimeViewMixin(ScaledTimeMixin, QWidgetMixin):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # pixels per beat
        self.__x_offset = 0

        self.setMinimumWidth(100)

        self.contentWidthChanged.connect(self.__contentWidthChanged)
        self.__contentWidthChanged(self.contentWidth())

    def __contentWidthChanged(self, width: int) -> None:
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.setXOffset(min(self.xOffset(), self.maximumXOffset()))

    def maximumXOffset(self) -> int:
        return max(0, self.contentWidth() - self.width())

    def pageWidth(self) -> int:
        return self.width()

    def xOffset(self) -> int:
        return self.__x_offset

    def setXOffset(self, offset: int) -> int:
        offset = max(0, min(offset, self.maximumXOffset()))
        if offset == self.__x_offset:
            return 0

        dx = self.__x_offset - offset
        self.__x_offset = offset
        self.xOffsetChanged.emit(self.__x_offset)
        return dx

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.pageWidthChanged.emit(self.width())
