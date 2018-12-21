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
from typing import Any, Optional

from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import slots
from . import canvas
from . import toolbox

logger = logging.getLogger(__name__)


class Frame(QtWidgets.QFrame):
    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent)

        self.setFrameStyle(QtWidgets.QFrame.Sunken | QtWidgets.QFrame.Panel)
        self.__layout = QtWidgets.QVBoxLayout()
        self.__layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.__layout.setContentsMargins(1, 1, 1, 1)
        self.setLayout(self.__layout)

    def setWidget(self, widget: QtWidgets.QWidget) -> None:
        self.__layout.addWidget(widget, 1)


class PipelineGraphView(ui_base.ProjectMixin, slots.SlotContainer, QtWidgets.QWidget):
    currentTrack, setCurrentTrack, currentTrackChanged = slots.slot(
        music.Track, 'currentTrack')

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        canvas_frame = Frame(parent=self)
        self.__canvas = canvas.Canvas(parent=canvas_frame, context=self.context)
        canvas_frame.setWidget(self.__canvas)

        self.__toolbox = toolbox.Toolbox(parent=self, context=self.context)
        self.__toolbox.toolChanged.connect(self.__canvas.toolChanged)
        self.__toolbox.resetViewTriggered.connect(self.__canvas.resetView)

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__toolbox)
        layout.addWidget(canvas_frame)
        self.setLayout(layout)

        self.currentTrackChanged.connect(self.__canvas.setCurrentTrack)
        self.__canvas.currentTrackChanged.connect(self.setCurrentTrack)
