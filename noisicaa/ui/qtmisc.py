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

import typing

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

if typing.TYPE_CHECKING:
    AbstractQWidget = QtWidgets.QWidget
else:
    AbstractQWidget = object


class QClickable(AbstractQWidget):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(evt)


class QFocusSignals(AbstractQWidget):
    focusGained = QtCore.pyqtSignal()
    focusLost = QtCore.pyqtSignal()

    def focusInEvent(self, evt: QtGui.QFocusEvent) -> None:
        self.focusGained.emit()
        super().focusInEvent(evt)

    def focusOutEvent(self, evt: QtGui.QFocusEvent) -> None:
        self.focusLost.emit()
        super().focusOutEvent(evt)


class QClickLabel(QClickable, QtWidgets.QLabel):
    pass
