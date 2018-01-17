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

import os.path

from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants


class MuteButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent, checkable=True, autoRaise=True)

        self._muted_icon = QtGui.QIcon(
            os.path.join(
                constants.DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QtGui.QIcon(
            os.path.join(
                constants.DATA_DIR, 'icons', 'track-not-muted.svg'))

        self.setIcon(self._not_muted_icon)
        self.toggled.connect(self.onToggled)

    def onToggled(self, checked):
        if checked:
            self.setIcon(self._muted_icon)
        else:
            self.setIcon(self._not_muted_icon)

