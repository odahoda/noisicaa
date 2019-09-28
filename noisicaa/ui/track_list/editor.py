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
import functools
import logging
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui import slots
from noisicaa.ui import ui_base
from noisicaa.ui import object_list_manager
from noisicaa.ui import player_state as player_state_lib
from noisicaa.builtin_nodes import ui_registry
from . import time_view_mixin
from . import base_track_editor
from . import tools

logger = logging.getLogger(__name__)


class Editor(
        object_list_manager.ObjectListManager[music.Track, base_track_editor.BaseTrackEditor],
        time_view_mixin.TimeViewMixin,
        ui_base.ProjectMixin,
        slots.SlotContainer,
        core.AutoCleanupMixin,
        QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    currentTrackChanged = QtCore.pyqtSignal(object)
    playbackPosition, setPlaybackPosition, playbackPositionChanged = slots.slot(
        audioproc.MusicalTime, 'playbackPosition', default=audioproc.MusicalTime(-1, 1))

    def __init__(self, *, player_state: player_state_lib.PlayerState, **kwargs: Any) -> None:
        self.__player_state = player_state

        self.__current_tool_box = None  # type: tools.ToolBox
        self.__current_tool = None  # type: tools.ToolBase
        self.__y_offset = 0

        super().__init__(**kwargs)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(0)

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.initObjectList(self.project, 'nodes')

        self.__content_height = 0
        self.updateTracks()
        self.objectListChanged.connect(self.updateTracks)

        self.__current_track = None  # type: music.Track

        for idx, track_editor in enumerate(self.objectWrappers()):
            if idx == 0:
                self.__onCurrentTrackChanged(track_editor.track)

        self.currentTrackChanged.connect(self.__onCurrentTrackChanged)

        self.__player_state.currentTimeChanged.connect(self.setPlaybackPosition)

        self.__increase_scale_x_action = QtWidgets.QAction(self)
        self.__increase_scale_x_action.setShortcut("ctrl+left")
        self.__increase_scale_x_action.setShortcutContext(Qt.WindowShortcut)
        self.__increase_scale_x_action.triggered.connect(
            functools.partial(self.__setScaleX, fractions.Fraction(2, 3)))
        self.addAction(self.__increase_scale_x_action)

        self.__decrease_scale_x_action = QtWidgets.QAction(self)
        self.__decrease_scale_x_action.setShortcut("ctrl+right")
        self.__decrease_scale_x_action.setShortcutContext(Qt.WindowShortcut)
        self.__decrease_scale_x_action.triggered.connect(
            functools.partial(self.__setScaleX, fractions.Fraction(3, 2)))
        self.addAction(self.__decrease_scale_x_action)

    def __setScaleX(self, factor: fractions.Fraction) -> None:
        new_scale_x = self.scaleX() * factor
        new_scale_x = max(fractions.Fraction(5, 1), new_scale_x)
        new_scale_x = min(fractions.Fraction(10000, 1), new_scale_x)

        center_time = max(0, self.width() // 2 - self.leftMargin() + self.xOffset()) / self.scaleX()

        self.setScaleX(new_scale_x)

        center_x = self.leftMargin() + int(self.scaleX() * center_time)
        self.setXOffset(max(0, center_x - self.width() // 2))

    def currentTrack(self) -> music.Track:
        return self.__current_track

    def setCurrentTrack(self, track: music.Track) -> None:
        if track is self.__current_track:
            return

        if self.__current_track is not None:
            track_editor = self.objectWrapperById(self.__current_track.id)
            track_editor.setIsCurrent(False)
            self.__current_track = None

        if track is not None:
            track_editor = self.objectWrapperById(track.id)
            track_editor.setIsCurrent(True)
            self.__current_track = track

            if track_editor.track.visible and self.isVisible():
                track_y = track_editor.y() + self.yOffset()
                yoffset = self.yOffset()
                if track_y + track_editor.height() > yoffset + self.height():
                    yoffset = track_y + track_editor.height() - self.height()
                if track_y < yoffset:
                    yoffset = track_y
                self.setYOffset(yoffset)

        self.currentTrackChanged.emit(self.__current_track)

    def _filterObject(self, obj: music.ObjectBase) -> bool:
        return isinstance(obj, music.Track)

    def _createObjectWrapper(self, track: music.Track) -> base_track_editor.BaseTrackEditor:
        track_editor_cls = ui_registry.track_editor_cls_map[type(track).__name__]
        track_editor = track_editor_cls(
            object_list_manager=self,
            wrapped_object=track,
            track=track,
            player_state=self.__player_state,
            editor=self,
            context=self.context)
        self.xOffsetChanged.connect(track_editor.setXOffset)
        self.scaleXChanged.connect(track_editor.setScaleX)
        self.playbackPositionChanged.connect(track_editor.setPlaybackPosition)
        track_editor.setXOffset(self.xOffset())

        self.__listeners['track:%s:visible' % track.id] = track.visible_changed.add(
            lambda *_: self.updateTracks())

        return track_editor

    def _deleteObjectWrapper(self, track_editor: base_track_editor.BaseTrackEditor) -> None:
        if track_editor.track is self.__current_track:
            self.setCurrentTrack(None)
        track_editor.hide()
        track_editor.cleanup()
        del self.__listeners['track:%s:visible' % track_editor.track.id]

    def updateTracks(self) -> None:
        y = 0
        for track_editor in self.objectWrappers():
            track_editor.setVisible(track_editor.track.visible)
            if not track_editor.track.visible:
                continue
            track_editor.setGeometry(0, y - self.yOffset(), self.width(), track_editor.height())
            y += track_editor.height()

        if y != self.__content_height:
            self.__content_height = y
            self.maximumYOffsetChanged.emit(
                max(0, self.__content_height - self.height()))

    def __onCurrentTrackChanged(self, track: music.Track) -> None:
        if track is not None:
            track_editor = self.objectWrapperById(track.id)
            self.setCurrentToolBox(track_editor.toolBox())

        else:
            self.setCurrentToolBox(None)

    def currentToolBox(self) -> tools.ToolBox:
        return self.__current_tool_box

    def setCurrentToolBox(self, toolbox: tools.ToolBox) -> None:
        if self.__current_tool_box is toolbox:
            return
        logger.debug("Switching to tool box %s", type(toolbox).__name__)

        if self.__current_tool_box is not None:
            self.__current_tool_box.currentToolChanged.disconnect(self.__onCurrentToolChanged)
            self.__onCurrentToolChanged(None)
            self.__current_tool_box = None

        if toolbox is not None:
            self.__current_tool_box = toolbox
            self.__onCurrentToolChanged(self.__current_tool_box.currentTool())
            self.__current_tool_box.currentToolChanged.connect(self.__onCurrentToolChanged)

        self.currentToolBoxChanged.emit(self.__current_tool_box)

    def __onCurrentToolChanged(self, tool: tools.ToolBase) -> None:
        if tool is self.__current_tool:
            return

        logger.debug("Current tool: %s", tool)

        if self.__current_tool is not None:
            self.__current_tool.cursorChanged.disconnect(self.__onToolCursorChanged)
            self.__onToolCursorChanged(None)
            self.__current_tool = None

        if tool is not None:
            self.__current_tool = tool
            self.__onToolCursorChanged(self.__current_tool.cursor())
            self.__current_tool.cursorChanged.connect(self.__onToolCursorChanged)

    def __onToolCursorChanged(self, cursor: QtGui.QCursor) -> None:
        logger.debug("Cursor changed: %s", cursor)
        if cursor is not None:
            self.setCursor(cursor)
        else:
            self.setCursor(QtGui.QCursor(Qt.ArrowCursor))

    def maximumYOffset(self) -> int:
        return max(0, self.__content_height - self.height())

    def pageHeight(self) -> int:
        return self.height()

    def yOffset(self) -> int:
        return self.__y_offset

    def setYOffset(self, offset: int) -> None:
        if offset == self.__y_offset:
            return

        self.__y_offset = offset
        self.yOffsetChanged.emit(self.__y_offset)

        self.updateTracks()

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), self.__y_offset)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.height())

        self.updateTracks()

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if evt.modifiers() == Qt.ShiftModifier:
            offset = self.xOffset()
            offset -= 2 * evt.angleDelta().y()
            offset = min(self.maximumXOffset(), offset)
            offset = max(0, offset)
            self.setXOffset(offset)
            evt.accept()
            return

        elif evt.modifiers() == Qt.ControlModifier:
            offset = self.yOffset()
            offset -= evt.angleDelta().y()
            offset = min(self.maximumYOffset(), offset)
            offset = max(0, offset)
            self.setYOffset(offset)
            evt.accept()
            return

        super().wheelEvent(evt)
