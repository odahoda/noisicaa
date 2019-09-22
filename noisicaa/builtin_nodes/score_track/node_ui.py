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
from noisicaa.ui import property_connector
from noisicaa.ui.graph import track_node
from . import model

logger = logging.getLogger(__name__)


class ScoreTrackWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QScrollArea):
    def __init__(self, track: model.ScoreTrack, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__track = track

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__transpose_octaves = QtWidgets.QSpinBox(body)
        self.__transpose_octaves.setVisible(True)
        self.__transpose_octaves.setKeyboardTracking(False)
        self.__transpose_octaves.setSuffix(' octaves')
        self.__transpose_octaves.setRange(-4, 4)
        self.__transpose_octaves.setSingleStep(1)
        connector = property_connector.QSpinBoxConnector(
            self.__transpose_octaves, self.__track, 'transpose_octaves',
            mutation_name='%s: Change transpose' % self.__track.name,
            context=self.context)
        self.add_cleanup_function(connector.cleanup)

        layout = QtWidgets.QFormLayout()
        layout.setVerticalSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("Transpose:", self.__transpose_octaves)
        body.setLayout(layout)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)


class ScoreTrackNode(track_node.TrackNode):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.ScoreTrack)
        self.__widget = None  # type: ScoreTrackWidget
        self.__track = node  # type: model.ScoreTrack

        super().__init__(
            node=node,
            icon=QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-score.svg')),
            **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = ScoreTrackWidget(track=self.__track, context=self.context)
        self.add_cleanup_function(self.__widget.cleanup)
        return self.__widget
