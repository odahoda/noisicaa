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

import logging
import os.path
from typing import Any

from PySide2.QtCore import Qt
from PySide2 import QtSvg
from PySide2 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.constants import DATA_DIR
from noisicaa.ui import ui_base
from noisicaa.ui.graph import track_node
from . import model

logger = logging.getLogger(__name__)


class PianoRollTrackWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QScrollArea):
    def __init__(self, track: model.PianoRollTrack, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__track = track

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        layout = QtWidgets.QFormLayout()
        layout.setVerticalSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        body.setLayout(layout)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)


class PianoRollTrackNode(track_node.TrackNode):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.PianoRollTrack)
        self.__widget = None  # type: PianoRollTrackWidget
        self.__track = node  # type: model.PianoRollTrack

        super().__init__(
            node=node,
            icon=QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-pianoroll.svg')),
            **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = PianoRollTrackWidget(track=self.__track, context=self.context)
        self.add_cleanup_function(self.__widget.cleanup)
        return self.__widget
