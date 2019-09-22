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

import functools
import logging
import uuid
from typing import Any, Tuple

from PySide2.QtCore import Qt
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import node_db
from .graph import view as graph_view
from . import ui_base
from . import render_dialog
from . import selection_set
from . import project_registry
from .track_list import view as track_list_view
from . import player_state as player_state_lib
from .track_list import measured_track_editor

logger = logging.getLogger(__name__)


class ProjectView(ui_base.AbstractProjectView):
    playingChanged = QtCore.Signal(bool)
    loopEnabledChanged = QtCore.Signal(bool)

    def __init__(
            self, *,
            project_connection: project_registry.Project,
            context: ui_base.CommonContext,
            **kwargs: Any) -> None:
        context = ui_base.ProjectContext(
            selection_set=selection_set.SelectionSet(),
            project_connection=project_connection,
            project_view=self,
            app=context.app)
        super().__init__(parent=None, context=context, **kwargs)

        self.__session_prefix = 'project-view:%016x:' % self.project.id

        self.__player_id = None  # type: str
        self.__player_realm = None  # type: str
        self.__player_node_id = None  # type: str
        self.__player_status_listener = None  # type: core.Listener
        self.__playback_pos_mode = 'follow'

        self.__player_state = player_state_lib.PlayerState(context=self.context)
        self.__player_state.playingChanged.connect(self.playingChanged)
        self.__player_state.loopEnabledChanged.connect(self.loopEnabledChanged)

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

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
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

    async def cleanup(self) -> None:
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

    def playing(self) -> bool:
        return self.__player_state.playing()

    def loopEnabled(self) -> bool:
        return self.__player_state.loopEnabled()

    def setPlaybackPosMode(self, mode: str) -> None:
        assert mode in ('follow', 'manual')
        self.__playback_pos_mode = mode

    async def createPluginUI(self, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self.project_client.create_plugin_ui(self.__player_id, node_id)

    async def deletePluginUI(self, node_id: str) -> None:
        await self.project_client.delete_plugin_ui(self.__player_id, node_id)

    async def sendNodeMessage(self, msg: audioproc.ProcessorMessage) -> None:
        await self.audioproc_client.send_node_messages(
            self.__player_realm, audioproc.ProcessorMessageList(messages=[msg]))

    def onPlayerMoveTo(self, where: str) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        new_time = None
        if where == 'start':
            new_time = audioproc.MusicalTime()

        elif where == 'end':
            new_time = self.time_mapper.end_time

        elif where == 'prev':
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

        elif where == 'next':
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

    def onPlayerToggle(self) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(playing=not self.__player_state.playing())))

    def onPlayerLoop(self, loop: bool) -> None:
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_enabled=loop)))

    def onClearSelection(self) -> None:
        self.__editor.onClearSelection()

    def onCopy(self) -> None:
        if self.selection_set.empty():
            return

        data = []
        items = [down_cast(measured_track_editor.MeasureEditor, item)
                 for item in self.selection_set]
        for item in sorted(items, key=lambda item: item.measure_reference.index):
            data.append(item.getCopy())

        self.app.setClipboardContent({'type': 'measures', 'data': data})

    def onPaste(self, *, mode: str) -> None:
        self.__track_list.onPaste(mode=mode)

    def onRender(self) -> None:
        dialog = render_dialog.RenderDialog(parent=self, context=self.context)
        dialog.setModal(True)
        dialog.show()

    def onSetNumMeasures(self) -> None:
        raise NotImplementedError
        # dialog = QtWidgets.QInputDialog(self)
        # dialog.setInputMode(QtWidgets.QInputDialog.IntInput)
        # dialog.setIntRange(1, 1000)
        # dialog.setIntValue(len(self.project.property_track.measure_list))
        # dialog.setLabelText("Number of measures:")
        # dialog.setWindowTitle("noisicaa - Set # measures")
        # dialog.accepted.connect(lambda: self.send_command_async(music.Command(
        #     target=self.project.id,
        #     set_num_measures=music.SetNumMeasures(num_measures=dialog.intValue()))))
        # dialog.show()

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
