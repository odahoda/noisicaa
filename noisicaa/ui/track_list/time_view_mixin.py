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


# These mixins should be subclasses of QtCore.QObject, but PyQt5 doesn't support multiple
# inheritance of QObjects.
# I'm forcing mypy to treat these as QObject instance, by adding asserts. But that also triggers
# "unreachable code" warnings.
# mypy: warn-unreachable=False

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
        assert isinstance(self, QtCore.QObject)
        if width == self.__content_width:
            return

        self.__content_width = width
        self.contentWidthChanged.emit(self.__content_width)

    def scaleX(self) -> fractions.Fraction:
        return self.__scale_x

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        assert isinstance(self, QtCore.QObject)
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.__updateContentWidth()
        self.scaleXChanged.emit(self.__scale_x)


class ContinuousTimeMixin(ScaledTimeMixin):
    def timeToX(self, time: audioproc.MusicalTime) -> int:
        return 10 + int(self.scaleX() * time.fraction)

    def xToTime(self, x: int) -> audioproc.MusicalTime:
        x -= 10
        if x <= 0:
            return audioproc.MusicalTime(0, 1)

        return audioproc.MusicalTime(x / self.scaleX())


class TimeViewMixin(ScaledTimeMixin):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        assert isinstance(self, QtCore.QObject)
        super().__init__(**kwargs)

        # pixels per beat
        self.__x_offset = 0

        self.setMinimumWidth(100)

        self.contentWidthChanged.connect(self.__contentWidthChanged)
        self.__contentWidthChanged(self.contentWidth())

    def __contentWidthChanged(self, width: int) -> None:
        assert isinstance(self, QtCore.QObject)
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.setXOffset(min(self.xOffset(), self.maximumXOffset()))

    def maximumXOffset(self) -> int:
        assert isinstance(self, QtCore.QObject)
        return max(0, self.contentWidth() - self.width())

    def pageWidth(self) -> int:
        assert isinstance(self, QtCore.QObject)
        return self.width()

    def xOffset(self) -> int:
        return self.__x_offset  # type: ignore

    def setXOffset(self, offset: int) -> None:
        assert isinstance(self, QtCore.QObject)
        offset = max(0, min(offset, self.maximumXOffset()))
        if offset == self.__x_offset:
            return

        dx = self.__x_offset - offset
        self.__x_offset = offset
        self.xOffsetChanged.emit(self.__x_offset)

        self.scroll(dx, 0)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        assert isinstance(self, QtCore.QObject)
        super().resizeEvent(evt)

        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.pageWidthChanged.emit(self.width())
