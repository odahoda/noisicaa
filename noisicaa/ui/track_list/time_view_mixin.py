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
from typing import Any

from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa import audioproc
from noisicaa.ui import ui_base

logger = logging.getLogger(__name__)


# This should be a subclass of QtCore.QObject, but PyQt5 doesn't support
# multiple inheritance of QObjects.
class ScaledTimeMixin(ui_base.ProjectMixin):
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

    def projectEndTime(self) -> audioproc.MusicalTime:
        return audioproc.MusicalTime() + self.project.duration

    def contentWidth(self) -> int:
        return self.__content_width

    def setContentWidth(self, width: int) -> None:
        if width == self.__content_width:
            return

        self.__content_width = width
        assert isinstance(self, QtCore.QObject)
        self.contentWidthChanged.emit(self.__content_width)

    def scaleX(self) -> fractions.Fraction:
        return self.__scale_x

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.__updateContentWidth()
        assert isinstance(self, QtCore.QObject)
        self.scaleXChanged.emit(self.__scale_x)


class ContinuousTimeMixin(ScaledTimeMixin):
    def timeToX(self, time: audioproc.MusicalTime) -> int:
        return 10 + int(self.scaleX() * time.fraction)

    def xToTime(self, x: int) -> audioproc.MusicalTime:
        x -= 10
        if x <= 0:
            return audioproc.MusicalTime(0, 1)

        return audioproc.MusicalTime(x / self.scaleX())


# TODO: This should really be a subclass of QtWidgets.QWidget, but somehow this screws up the
#   signals... Because of that, there are a bunch of 'type: ignore' overrides below.
class TimeViewMixin(ScaledTimeMixin):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # pixels per beat
        self.__x_offset = 0

        self.setMinimumWidth(100)  # type: ignore

        assert isinstance(self, QtCore.QObject)
        self.contentWidthChanged.connect(self.__contentWidthChanged)

    def __contentWidthChanged(self, width: int) -> None:
        assert isinstance(self, QtCore.QObject)
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.setXOffset(min(self.xOffset(), self.maximumXOffset()))

    def maximumXOffset(self) -> int:
        return max(0, self.contentWidth() - self.width())  # type: ignore

    def pageWidth(self) -> int:
        return self.width()  # type: ignore

    def xOffset(self) -> int:
        return self.__x_offset

    def setXOffset(self, offset: int) -> None:
        offset = max(0, min(offset, self.maximumXOffset()))
        if offset == self.__x_offset:
            return

        dx = self.__x_offset - offset
        self.__x_offset = offset
        assert isinstance(self, QtCore.QObject)
        self.xOffsetChanged.emit(self.__x_offset)

        self.scroll(dx, 0)  # type: ignore

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)  # type: ignore

        assert isinstance(self, QtCore.QObject)
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.pageWidthChanged.emit(self.width())  # type: ignore
