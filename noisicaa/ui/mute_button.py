#!/usr/bin/python3

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

