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
import functools
import logging
import uuid
import typing
from typing import Any, Dict, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import node_db
from .graph import view as graph_view
from . import ui_base
from . import render_dialog
from . import project_registry
from .track_list import view as track_list_view
from . import player_state as player_state_lib
from . import vumeter
from . import slots
from . import engine_state

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class TimeDisplay(slots.SlotContainer, QtWidgets.QLCDNumber):
    class DisplayMode(enum.IntEnum):
        MusicalTime = 0
        RealTime = 1

    displayMode, setDisplayMode, displayModeChanged = slots.slot(
        DisplayMode, 'displayMode', default=DisplayMode.MusicalTime)

    def __init__(
            self, parent: QtWidgets.QWidget, time_mapper: audioproc.TimeMapper, **kwargs: Any
    ) -> None:
        super().__init__(parent=parent, **kwargs)

        self.setDigitCount(9)
        self.setSegmentStyle(QtWidgets.QLCDNumber.Flat)
        self.setFrameStyle(QtWidgets.QFrame.Panel)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)

        self.__time_mapper = time_mapper
        self.__current_time = audioproc.MusicalTime()

        self.displayModeChanged.connect(self.__update)

    def __update(self) -> None:
        if self.displayMode() == self.DisplayMode.MusicalTime:
            beat = self.__current_time / audioproc.MusicalDuration(1, 4)
            self.display('%.3f' % beat)

        else:
            assert self.displayMode() == self.DisplayMode.RealTime
            t = (self.__time_mapper.musical_to_sample_time(self.__current_time)
                 / self.__time_mapper.sample_rate)
            millis = int(1000 * t) % 1000
            seconds = int(t) % 60
            minutes = int(t) // 60
            self.display('%d:%02d.%03d' % (minutes, seconds, millis))

    def setCurrentTime(self, current_time: audioproc.MusicalTime) -> None:
        self.__current_time = current_time
        self.__update()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            if self.displayMode() == self.DisplayMode.MusicalTime:
                self.setDisplayMode(self.DisplayMode.RealTime)
            else:
                self.setDisplayMode(self.DisplayMode.MusicalTime)
            evt.accept()
            return

        super().mousePressEvent(evt)


class ProjectView(ui_base.AbstractProjectView):
    playingChanged = QtCore.pyqtSignal(bool)
    loopEnabledChanged = QtCore.pyqtSignal(bool)

    def __init__(
            self, *,
            project_connection: project_registry.Project,
            context: ui_base.CommonContext,
            **kwargs: Any) -> None:
        context = ui_base.ProjectContext(
            project_connection=project_connection,
            project_view=self,
            app=context.app)
        super().__init__(parent=None, context=context, **kwargs)

        self.__session_prefix = 'project-view:%016x:' % self.project.id

        self.__player_id = None  # type: str
        self.__player_realm = None  # type: str
        self.__player_node_id = None  # type: str
        self.__player_status_listener = None  # type: core.Listener
        self.__vumeter_node_id = None  # type: str
        self.__vumeter_listener = None  # type: core.Listener

        self.__player_state = player_state_lib.PlayerState(context=self.context)

        self.__track_list = track_list_view.TrackListView(
            project_view=self, player_state=self.__player_state,
            parent=self, context=self.context)

        self.__graph = graph_view.GraphView(parent=self, context=self.context)

        self.__track_list.currentTrackChanged.connect(self.__graph.setCurrentTrack)
        self.__graph.currentTrackChanged.connect(self.__track_list.setCurrentTrack)

        self.__splitter = QtWidgets.QSplitter(self)
        self.__splitter.setOrientation(Qt.Vertical)
        self.__splitter.setHandleWidth(10)
        self.__splitter.addWidget(self.__track_list)
        self.__splitter.setCollapsible(0, False)
        self.__splitter.addWidget(self.__graph)

        self.__time_display = TimeDisplay(self, self.time_mapper)
        self.__time_display.setMinimumWidth(9*20)
        self.__player_state.currentTimeChanged.connect(self.__time_display.setCurrentTime)
        self.__time_display.setCurrentTime(self.__player_state.currentTime())
        self.__time_display.setDisplayMode(TimeDisplay.DisplayMode(self.get_session_value(
            self.__session_prefix + 'time-display-mode', TimeDisplay.DisplayMode.MusicalTime)))
        self.__time_display.displayModeChanged.connect(functools.partial(
            self.set_session_value, self.__session_prefix + 'time-display-mode'))

        self.__vumeter = vumeter.VUMeter(self)
        self.__vumeter.setMinimumWidth(250)

        self.__engine_load = engine_state.LoadHistory(self, self.app.engine_state)
        self.__engine_load.setFixedWidth(100)

        self.__toggle_playback_button = QtWidgets.QToolButton(self)
        self.__toggle_playback_button.setDefaultAction(self.__player_state.togglePlaybackAction())
        self.__toggle_playback_button.setIconSize(QtCore.QSize(54, 54))
        self.__toggle_playback_button.setAutoRaise(True)

        self.__toggle_loop_button = QtWidgets.QToolButton(self)
        self.__toggle_loop_button.setDefaultAction(self.__player_state.toggleLoopAction())
        self.__toggle_loop_button.setIconSize(QtCore.QSize(24, 24))
        self.__toggle_loop_button.setAutoRaise(True)

        self.__move_to_start_button = QtWidgets.QToolButton(self)
        self.__move_to_start_button.setDefaultAction(self.__player_state.moveToStartAction())
        self.__move_to_start_button.setIconSize(QtCore.QSize(24, 24))
        self.__move_to_start_button.setAutoRaise(True)

        self.__move_to_end_button = QtWidgets.QToolButton(self)
        self.__move_to_end_button.setDefaultAction(self.__player_state.moveToEndAction())
        self.__move_to_end_button.setIconSize(QtCore.QSize(24, 24))
        self.__move_to_end_button.setAutoRaise(True)

        self.__move_to_prev_button = QtWidgets.QToolButton(self)
        self.__move_to_prev_button.setDefaultAction(self.__player_state.moveToPrevAction())
        self.__move_to_prev_button.setIconSize(QtCore.QSize(24, 24))
        self.__move_to_prev_button.setAutoRaise(True)

        self.__move_to_next_button = QtWidgets.QToolButton(self)
        self.__move_to_next_button.setDefaultAction(self.__player_state.moveToNextAction())
        self.__move_to_next_button.setIconSize(QtCore.QSize(24, 24))
        self.__move_to_next_button.setAutoRaise(True)

        tb_layout = QtWidgets.QGridLayout()
        tb_layout.setContentsMargins(0, 2, 0, 2)
        tb_layout.setSpacing(0)
        c = 0
        tb_layout.addWidget(self.__toggle_playback_button, 0, c, 2, 1)
        c += 1
        tb_layout.addItem(QtWidgets.QSpacerItem(4, 4), 0, c, 2, 1)
        c += 1
        tb_layout.addWidget(self.__toggle_loop_button, 0, c, 1, 1)
        c += 1
        tb_layout.addItem(QtWidgets.QSpacerItem(4, 4), 0, c, 2, 1)
        c += 1
        tb_layout.addWidget(self.__move_to_start_button, 0, c, 1, 1)
        tb_layout.addWidget(self.__move_to_prev_button, 1, c, 1, 1)
        c += 1
        tb_layout.addWidget(self.__move_to_end_button, 0, c, 1, 1)
        tb_layout.addWidget(self.__move_to_next_button, 1, c, 1, 1)
        c += 1
        tb_layout.addItem(QtWidgets.QSpacerItem(4, 4), 0, c, 2, 1)
        c += 1
        tb_layout.addWidget(self.__time_display, 0, c, 2, 1)
        c += 1
        tb_layout.addItem(QtWidgets.QSpacerItem(4, 4), 0, c, 2, 1)
        c += 1
        tb_layout.addWidget(self.__vumeter, 0, c, 2, 1)
        c += 1
        tb_layout.setColumnStretch(c, 1)
        c += 1
        tb_layout.addWidget(self.__engine_load, 0, c, 2, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(tb_layout)
        layout.addWidget(self.__splitter)
        self.setLayout(layout)

    async def setup(self) -> None:
        self.__player_id, self.__player_realm = await self.project_client.create_player(
            audioproc_address=self.audioproc_client.address)
        self.__player_status_listener = self.audioproc_client.player_state_changed.add(
            self.__player_realm, self.__player_state.updateFromProto)

        self.__track_list.setPlayerID(self.__player_id)
        self.__player_state.setPlayerID(self.__player_id)

        await self.project_client.update_player_state(
            self.__player_id,
            audioproc.PlayerState(
                current_time=self.__player_state.currentTimeProto(),
                loop_enabled=self.__player_state.loopEnabled(),
                loop_start_time=self.__player_state.loopStartTimeProto(),
                loop_end_time=self.__player_state.loopEndTimeProto()))

        self.__player_node_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            'root',
            id=self.__player_node_id,
            child_realm=self.__player_realm,
            description=node_db.Builtins.ChildRealmDescription)
        await self.audioproc_client.connect_ports(
            'root',
            self.__player_node_id, 'out:left',
            'sink', 'in:left',
            node_db.PortDescription.AUDIO)
        await self.audioproc_client.connect_ports(
            'root',
            self.__player_node_id, 'out:right',
            'sink', 'in:right',
            node_db.PortDescription.AUDIO)

        self.__vumeter_node_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            'root',
            id=self.__vumeter_node_id,
            description=self.project.get_node_description('builtin://vumeter'))
        await self.audioproc_client.connect_ports(
            'root',
            self.__player_node_id, 'out:left',
            self.__vumeter_node_id, 'in:left',
            node_db.PortDescription.AUDIO)
        await self.audioproc_client.connect_ports(
            'root',
            self.__player_node_id, 'out:right',
            self.__vumeter_node_id, 'in:right',
            node_db.PortDescription.AUDIO)

        self.__vumeter_listener = self.audioproc_client.node_messages.add(
            self.__vumeter_node_id, self.__vumeterMessage)

    async def cleanup(self) -> None:
        if self.__vumeter_listener is not None:
            self.__vumeter_listener.remove()
            self.__vumeter_listener = None

        if self.__vumeter_node_id is not None:
            assert self.__player_node_id is not None
            await self.audioproc_client.disconnect_ports(
                'root', self.__player_node_id, 'out:left', self.__vumeter_node_id, 'in:left')
            await self.audioproc_client.disconnect_ports(
                'root', self.__player_node_id, 'out:right', self.__vumeter_node_id, 'in:right')
            await self.audioproc_client.remove_node(
                'root', self.__vumeter_node_id)
            self.__vumeter_node_id = None

        if self.__player_node_id is not None:
            await self.audioproc_client.disconnect_ports(
                'root', self.__player_node_id, 'out:left', 'sink', 'in:left')
            await self.audioproc_client.disconnect_ports(
                'root', self.__player_node_id, 'out:right', 'sink', 'in:right')
            await self.audioproc_client.remove_node(
                'root', self.__player_node_id)
            self.__player_node_id = None

        if self.__player_status_listener is not None:
            self.__player_status_listener.remove()
            self.__player_status_listener = None

        if self.__player_id is not None:
            self.__track_list.setPlayerID(None)
            await self.project_client.delete_player(self.__player_id)
            self.__player_id = None
            self.__player_realm = None

        self.__track_list.cleanup()

    def playerState(self) -> player_state_lib.PlayerState:
        return self.__player_state

    async def createPluginUI(self, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self.project_client.create_plugin_ui(self.__player_id, node_id)

    async def deletePluginUI(self, node_id: str) -> None:
        await self.project_client.delete_plugin_ui(self.__player_id, node_id)

    async def sendNodeMessage(self, msg: audioproc.ProcessorMessage) -> None:
        await self.audioproc_client.send_node_messages(
            self.__player_realm, audioproc.ProcessorMessageList(messages=[msg]))

    def __vumeterMessage(self, msg: Dict[str, Any]) -> None:
        meter = 'http://noisicaa.odahoda.de/lv2/processor_vumeter#meter'
        if meter in msg:
            current_left, peak_left, current_right, peak_right = msg[meter]
            self.__vumeter.setLeftValue(current_left)
            self.__vumeter.setLeftPeak(peak_left)
            self.__vumeter.setRightValue(current_right)
            self.__vumeter.setRightPeak(peak_right)

    def onRender(self) -> None:
        dialog = render_dialog.RenderDialog(parent=self, context=self.context)
        dialog.setModal(True)
        dialog.show()

    def onSetBPM(self) -> None:
        dialog = QtWidgets.QInputDialog(self)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)
        dialog.setIntRange(1, 1000)
        dialog.setIntValue(self.project.bpm)
        dialog.setLabelText("BPM:")
        dialog.setWindowTitle("noisicaa - Set BPM")
        dialog.accepted.connect(
            functools.partial(self.__onSetBPMDone, dialog))
        dialog.show()

    def __onSetBPMDone(self, dialog: QtWidgets.QInputDialog) -> None:
        with self.project.apply_mutations('Change BPM'):
            self.project.bpm = dialog.intValue()

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        super().showEvent(evt)

        splitter_state = self.get_session_value(self.__session_prefix + 'splitter-state', None)
        if splitter_state:
            self.__splitter.restoreState(splitter_state)

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        super().hideEvent(evt)

        self.set_session_value(
            self.__session_prefix + 'splitter-state', self.__splitter.saveState().data())
