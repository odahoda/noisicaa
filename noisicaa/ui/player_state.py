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

import enum
import logging
import os.path
import time as time_lib
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from noisicaa import audioproc
from noisicaa.audioproc.public import musical_time_pb2
from . import ui_base

logger = logging.getLogger(__name__)


class TimeMode(enum.Enum):
    Follow = 0
    Manual = 1


class MoveTo(enum.Enum):
    Start = 0
    End = 1
    PrevBeat = 2
    NextBeat = 3


class PlayerState(ui_base.ProjectMixin, QtCore.QObject):
    playingChanged = QtCore.pyqtSignal(bool)
    currentTimeChanged = QtCore.pyqtSignal(object)
    loopStartTimeChanged = QtCore.pyqtSignal(object)
    loopEndTimeChanged = QtCore.pyqtSignal(object)
    loopEnabledChanged = QtCore.pyqtSignal(bool)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__session_prefix = 'player_state:%s:' % self.project.id
        self.__last_current_time_update = None  # type: float

        self.__time_mode = TimeMode.Follow

        self.__playing = False
        self.__current_time = self.__get_session_value('current_time', audioproc.MusicalTime())
        self.__loop_start_time = self.__get_session_value('loop_start_time', None)
        self.__loop_end_time = self.__get_session_value('loop_end_time', None)
        self.__loop_enabled = self.__get_session_value('loop_enabled', False)

        self.__player_id = None  # type: str

        self.__move_to_start_action = QtWidgets.QAction("Move to start", self)
        self.__move_to_start_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-skip-backward.svg')))
        self.__move_to_start_action.setShortcut(QtGui.QKeySequence('Home'))
        self.__move_to_start_action.setShortcutContext(Qt.ApplicationShortcut)
        self.__move_to_start_action.triggered.connect(lambda: self.__onMoveTo(MoveTo.Start))

        self.__move_to_end_action = QtWidgets.QAction("Move to end", self)
        self.__move_to_end_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-skip-forward.svg')))
        self.__move_to_end_action.setShortcut(QtGui.QKeySequence('End'))
        self.__move_to_end_action.setShortcutContext(Qt.ApplicationShortcut)
        self.__move_to_end_action.triggered.connect(lambda: self.__onMoveTo(MoveTo.End))

        self.__move_to_prev_action = QtWidgets.QAction("Move to previous beat", self)
        self.__move_to_prev_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-seek-backward.svg')))
        self.__move_to_prev_action.setShortcut(QtGui.QKeySequence('PgUp'))
        self.__move_to_prev_action.setShortcutContext(Qt.ApplicationShortcut)
        self.__move_to_prev_action.triggered.connect(lambda: self.__onMoveTo(MoveTo.PrevBeat))

        self.__move_to_next_action = QtWidgets.QAction("Move to next beat", self)
        self.__move_to_next_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-seek-forward.svg')))
        self.__move_to_next_action.setShortcut(QtGui.QKeySequence('PgDown'))
        self.__move_to_next_action.setShortcutContext(Qt.ApplicationShortcut)
        self.__move_to_next_action.triggered.connect(lambda: self.__onMoveTo(MoveTo.NextBeat))

        self.__toggle_action = QtWidgets.QAction("Play", self)
        self.__toggle_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-playback-start.svg')))
        self.__toggle_action.setShortcut(QtGui.QKeySequence('Space'))
        self.__toggle_action.setShortcutContext(Qt.ApplicationShortcut)
        self.__toggle_action.triggered.connect(self.__onToggle)

        self.__loop_action = QtWidgets.QAction("Loop playback", self)
        self.__loop_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'media-playlist-repeat.svg')))
        self.__loop_action.setCheckable(True)
        self.__loop_action.toggled.connect(self.__onLoop)

    def __get_session_value(self, key: str, default: Any) -> Any:
        return self.get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key: str, value: Any) -> None:
        self.set_session_value(self.__session_prefix + key, value)

    def playerID(self) -> str:
        return self.__player_id

    def setPlayerID(self, player_id: str) -> None:
        self.__player_id = player_id

    def updateFromProto(self, player_state: audioproc.PlayerState) -> None:
        if player_state.HasField('current_time') and self.__time_mode == TimeMode.Follow:
            self.setCurrentTime(audioproc.MusicalTime.from_proto(player_state.current_time))

        if player_state.HasField('playing') and self.__time_mode == TimeMode.Follow:
            self.setPlaying(player_state.playing)

        if player_state.HasField('loop_enabled'):
            self.setLoopEnabled(player_state.loop_enabled)

        if player_state.HasField('loop_start_time'):
            self.setLoopStartTime(audioproc.MusicalTime.from_proto(player_state.loop_start_time))

        if player_state.HasField('loop_end_time'):
            self.setLoopEndTime(audioproc.MusicalTime.from_proto(player_state.loop_end_time))

    def populateToolBar(self, toolbar: QtWidgets.QToolBar) -> None:
        toolbar.addAction(self.__toggle_action)
        toolbar.addAction(self.__loop_action)
        toolbar.addSeparator()
        toolbar.addAction(self.__move_to_start_action)
        toolbar.addAction(self.__move_to_end_action)

    def setTimeMode(self, mode: TimeMode) -> None:
        self.__time_mode = mode

    def setPlaying(self, playing: bool) -> None:
        if playing == self.__playing:
            return

        if playing:
            self.__toggle_action.setIcon(
                QtGui.QIcon(os.path.join(constants.DATA_DIR, 'icons', 'media-playback-pause.svg')))
        else:
            self.__toggle_action.setIcon(
                QtGui.QIcon(os.path.join(constants.DATA_DIR, 'icons', 'media-playback-start.svg')))

        self.__playing = playing
        self.playingChanged.emit(playing)

    def playing(self) -> bool:
        return self.__playing

    def setCurrentTime(self, current_time: audioproc.MusicalTime) -> None:
        if current_time == self.__current_time:
            return

        self.__current_time = current_time
        if (self.__last_current_time_update is None
                or time_lib.time() - self.__last_current_time_update > 5):
            self.__set_session_value('current_time', current_time)
            self.__last_current_time_update = time_lib.time()
        self.currentTimeChanged.emit(current_time)

    def currentTime(self) -> audioproc.MusicalTime:
        return self.__current_time

    def currentTimeProto(self) -> musical_time_pb2.MusicalTime:
        return self.__current_time.to_proto()

    def setLoopStartTime(self, loop_start_time: audioproc.MusicalTime) -> None:
        if loop_start_time == self.__loop_start_time:
            return

        self.__loop_start_time = loop_start_time
        self.__set_session_value('loop_start_time', loop_start_time)
        self.loopStartTimeChanged.emit(loop_start_time)

    def loopStartTime(self) -> audioproc.MusicalTime:
        return self.__loop_start_time

    def loopStartTimeProto(self) -> musical_time_pb2.MusicalTime:
        if self.__loop_start_time is not None:
            return self.__loop_start_time.to_proto()
        else:
            return None

    def setLoopEndTime(self, loop_end_time: audioproc.MusicalTime) -> None:
        if loop_end_time == self.__loop_end_time:
            return

        self.__loop_end_time = loop_end_time
        self.__set_session_value('loop_end_time', loop_end_time)
        self.loopEndTimeChanged.emit(loop_end_time)

    def loopEndTime(self) -> audioproc.MusicalTime:
        return self.__loop_end_time

    def loopEndTimeProto(self) -> musical_time_pb2.MusicalTime:
        if self.__loop_end_time is not None:
            return self.__loop_end_time.to_proto()
        else:
            return None

    def setLoopEnabled(self, loop_enabled: bool) -> None:
        loop_enabled = bool(loop_enabled)
        if loop_enabled == self.__loop_enabled:
            return

        self.__loop_action.setChecked(loop_enabled)

        self.__loop_enabled = loop_enabled
        self.__set_session_value('loop_enabled', loop_enabled)
        self.loopEnabledChanged.emit(loop_enabled)

    def loopEnabled(self) -> bool:
        return self.__loop_enabled

    def __onMoveTo(self, where: MoveTo) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        new_time = None
        if where == MoveTo.Start:
            new_time = audioproc.MusicalTime()

        elif where == MoveTo.End:
            new_time = self.time_mapper.end_time

        elif where == MoveTo.PrevBeat:
            raise NotImplementedError
            # measure_start_time = audioproc.MusicalTime()
            # current_time = self.__player_state.currentTime()
            # for mref in self.project.property_track.measure_list:
            #     measure = mref.measure
            #     if measure_start_time <= current_time < (measure_start_time + measure.duration
            #                                              + audioproc.MusicalDuration(1, 16)):
            #         new_time = measure_start_time
            #         break

            #     measure_start_time += measure.duration

        elif where == MoveTo.NextBeat:
            raise NotImplementedError
            # measure_start_time = audioproc.MusicalTime()
            # current_time = self.__player_state.currentTime()
            # for mref in self.project.property_track.measure_list:
            #     measure = mref.measure
            #     if measure_start_time <= current_time < measure_start_time + measure.duration:
            #         new_time = measure_start_time + measure.duration
            #         break

            #     measure_start_time += measure.duration

        else:
            raise ValueError(where)

        if new_time is not None:
            self.call_async(
                self.project_client.update_player_state(
                    self.__player_id,
                    audioproc.PlayerState(current_time=new_time.to_proto())))

    def __onToggle(self) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(playing=not self.__playing)))

    def __onLoop(self, loop: bool) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_enabled=loop)))
