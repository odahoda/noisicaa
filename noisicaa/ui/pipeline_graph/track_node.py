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
import os.path
from typing import cast, Any

from PyQt5 import QtSvg
from PyQt5 import QtWidgets

from noisicaa.constants import DATA_DIR
from noisicaa import music

from . import base_node

logger = logging.getLogger(__name__)


class TrackNode(base_node.Node):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        if isinstance(node, music.ScoreTrack):
            icon = QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-score.svg'))
        elif isinstance(node, music.BeatTrack):
            icon = QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-beat.svg'))
        elif isinstance(node, music.ControlTrack):
            icon = QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-control.svg'))
        elif isinstance(node, music.SampleTrack):
            icon = QtSvg.QSvgRenderer(os.path.join(DATA_DIR, 'icons', 'track-type-sample.svg'))
        else:
            raise ValueError(type(node))

        super().__init__(node=node, icon=icon, **kwargs)

        self.__track = cast(music.Track, node)

        self.__show_track_action = QtWidgets.QAction("Show track")
        self.__show_track_action.setCheckable(True)
        self.__show_track_action.setChecked(self.__track.visible)
        self.__show_track_action.toggled.connect(self.setTrackVisiblity)

    def buildContextMenu(self, menu: QtWidgets.QMenu) -> None:
        menu.addAction(self.__show_track_action)
        super().buildContextMenu(menu)

    def setTrackVisiblity(self, visible: bool) -> None:
        if visible == self.__track.visible:
            return

        self.send_command_async(music.Command(
            target=self.__track.id,
            update_track=music.UpdateTrack(
                visible=visible)))
