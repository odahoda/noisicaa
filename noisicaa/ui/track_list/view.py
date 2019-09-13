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
import time as time_lib
import typing
from typing import Any, Optional, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import slots
from noisicaa.ui import player_state as player_state_lib
from . import editor
from . import time_line
from . import toolbox

if typing.TYPE_CHECKING:
    from noisicaa.ui import project_view as project_view_lib

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


class TrackListView(ui_base.ProjectMixin, slots.SlotContainer, QtWidgets.QSplitter):
    playingChanged = QtCore.pyqtSignal(bool)
    loopEnabledChanged = QtCore.pyqtSignal(bool)

    currentTrack, setCurrentTrack, currentTrackChanged = slots.slot(
        music.Track, 'currentTrack')

    def __init__(
            self, *,
            project_view: 'project_view_lib.ProjectView',
            player_state: player_state_lib.PlayerState,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__project_view = project_view
        self.__player_state = player_state

        self.__session_prefix = 'tracklist:%s:' % self.project.id
        self.__session_data_last_update = {}  # type: Dict[str, float]

        editor_frame = Frame(self)
        self.__editor = editor.Editor(
            player_state=self.__player_state,
            parent=editor_frame, context=self.context)
        editor_frame.setWidget(self.__editor)

        self.__editor.currentTrackChanged.connect(self.setCurrentTrack)
        self.currentTrackChanged.connect(self.__editor.setCurrentTrack)

        self.__editor.setScaleX(self.__get_session_value('scale_x', self.__editor.scaleX()))
        self.__editor.setXOffset(self.__get_session_value('x_offset', 0))
        self.__editor.setYOffset(self.__get_session_value('y_offset', 0))

        self.__editor.scaleXChanged.connect(self.__updateScaleX)

        time_line_frame = Frame(self)
        self.__time_line = time_line.TimeLine(
            project_view=self.__project_view, player_state=self.__player_state,
            parent=time_line_frame, context=self.context)
        time_line_frame.setWidget(self.__time_line)

        self.__time_line.setScaleX(self.__editor.scaleX())
        self.__time_line.setXOffset(self.__editor.xOffset())
        self.__editor.scaleXChanged.connect(self.__time_line.setScaleX)

        scroll_x = QtWidgets.QScrollBar(orientation=Qt.Horizontal, parent=self)
        scroll_x.setRange(0, self.__editor.maximumXOffset())
        scroll_x.setSingleStep(50)
        scroll_x.setPageStep(self.__editor.pageWidth())
        scroll_x.setValue(self.__editor.xOffset())
        scroll_y = QtWidgets.QScrollBar(orientation=Qt.Vertical, parent=self)
        scroll_y.setRange(0, self.__editor.maximumYOffset())
        scroll_y.setSingleStep(20)
        scroll_y.setPageStep(self.__editor.pageHeight())
        scroll_y.setValue(self.__editor.yOffset())

        self.__editor.maximumXOffsetChanged.connect(scroll_x.setMaximum)
        self.__editor.pageWidthChanged.connect(scroll_x.setPageStep)
        self.__editor.xOffsetChanged.connect(scroll_x.setValue)
        self.__time_line.xOffsetChanged.connect(scroll_x.setValue)
        scroll_x.valueChanged.connect(self.__editor.setXOffset)
        scroll_x.valueChanged.connect(self.__time_line.setXOffset)
        scroll_x.valueChanged.connect(self.__updateXOffset)

        self.__editor.maximumYOffsetChanged.connect(scroll_y.setMaximum)
        self.__editor.pageHeightChanged.connect(scroll_y.setPageStep)
        self.__editor.yOffsetChanged.connect(scroll_y.setValue)
        scroll_y.valueChanged.connect(self.__editor.setYOffset)
        scroll_y.valueChanged.connect(self.__updateYOffset)

        self.setMinimumHeight(time_line_frame.minimumHeight())

        editor_pane = QtWidgets.QWidget(self)
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(time_line_frame, 0, 0, 1, 1)
        layout.addWidget(editor_frame, 1, 0, 1, 1)
        layout.addWidget(scroll_x, 2, 0, 1, 1)
        layout.addWidget(scroll_y, 1, 1, 1, 1)
        editor_pane.setLayout(layout)

        self.__toolbox = toolbox.Toolbox(parent=self, context=self.context)
        self.__toolbox.setCurrentToolBox(self.__editor.currentToolBox())
        self.__editor.currentToolBoxChanged.connect(self.__toolbox.setCurrentToolBox)

        self.addWidget(self.__toolbox)
        self.setStretchFactor(0, 0)
        self.addWidget(editor_pane)
        self.setStretchFactor(1, 1)
        self.setCollapsible(1, False)

    def __get_session_value(self, key: str, default: Any) -> Any:
        return self.get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key: str, value: Any) -> None:
        self.set_session_value(self.__session_prefix + key, value)

    def __lazy_set_session_value(self, key: str, value: Any) -> None:
        # TODO: value should be stored to session 5sec after most recent change. I.e. need
        #   some timer...
        last_time = self.__session_data_last_update.get(key, 0)
        if time_lib.time() - last_time > 5:
            self.__set_session_value(key, value)
            self.__session_data_last_update[key] = time_lib.time()

    def __updateScaleX(self, scale: fractions.Fraction) -> None:
        self.__set_session_value('scale_x', scale)

    def __updateXOffset(self, offset: int) -> None:
        self.__lazy_set_session_value('x_offset', offset)

    def __updateYOffset(self, offset: int) -> None:
        self.__lazy_set_session_value('y_offset', offset)

    def setPlayerID(self, player_id: str) -> None:
        self.__time_line.setPlayerID(player_id)

    def cleanup(self) -> None:
        self.__editor.cleanup()
