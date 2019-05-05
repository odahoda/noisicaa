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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtSvg
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model_base
from noisicaa import music
from noisicaa.constants import DATA_DIR
from noisicaa.ui import ui_base
from noisicaa.ui.graph import track_node
from . import model

logger = logging.getLogger(__name__)


class ScoreTrackWidget(ui_base.ProjectMixin, QtWidgets.QScrollArea):
    def __init__(self, track: model.ScoreTrack, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__track = track

        self.__listeners = {}  # type: Dict[str, core.Listener]

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__transpose_octaves = QtWidgets.QSpinBox(body)
        self.__transpose_octaves.setSuffix(' octaves')
        self.__transpose_octaves.setRange(-4, 4)
        self.__transpose_octaves.setSingleStep(1)
        self.__transpose_octaves.valueChanged.connect(self.onTransposeOctavesEdited)
        self.__transpose_octaves.setVisible(True)
        self.__transpose_octaves.setValue(self.__track.transpose_octaves)
        self.__listeners['track:transpose_octaves'] = (
            self.__track.transpose_octaves_changed.add(self.onTransposeOctavesChanged))

        layout = QtWidgets.QFormLayout()
        layout.setVerticalSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("Transpose:", self.__transpose_octaves)
        body.setLayout(layout)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)

    def cleanup(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

    def onTransposeOctavesChanged(self, change: model_base.PropertyValueChange[int]) -> None:
        self.__transpose_octaves.setValue(change.new_value)

    def onTransposeOctavesEdited(self, transpose_octaves: int) -> None:
        if transpose_octaves != self.__track.transpose_octaves:
            with self.project.apply_mutations():
                self.__track.transpose_octaves = transpose_octaves


class ScoreTrackNode(track_node.TrackNode):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.ScoreTrack)
        self.__widget = None  # type: ScoreTrackWidget
        self.__track = node  # type: model.ScoreTrack

        super().__init__(
            node=node,
            icon=QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-score.svg')),
            **kwargs)

    def cleanup(self) -> None:
        if self.__widget is not None:
            self.__widget.cleanup()
        super().cleanup()

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = ScoreTrackWidget(track=self.__track, context=self.context)
        return self.__widget
