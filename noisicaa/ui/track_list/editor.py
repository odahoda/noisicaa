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
from typing import cast, Any, Dict, List, Type

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import player_state as player_state_lib
from noisicaa.builtin_nodes import ui_registry
from . import time_view_mixin
from . import base_track_editor
from . import measured_track_editor
from . import tools

logger = logging.getLogger(__name__)


class Editor(
        time_view_mixin.TimeViewMixin, ui_base.ProjectMixin, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, *, player_state: player_state_lib.PlayerState, **kwargs: Any) -> None:
        self.__player_state = player_state

        self.__current_tool_box = None  # type: tools.ToolBox
        self.__current_tool = None  # type: tools.ToolBase
        self.__current_track_editor = None  # type: base_track_editor.BaseTrackEditor
        self.__y_offset = 0

        super().__init__(**kwargs)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(0)

        self.__viewport = QtWidgets.QWidget(self)
        self.__viewport.move(0, 0)

        self.__viewport_layout = QtWidgets.QVBoxLayout()
        self.__viewport_layout.setContentsMargins(0, 0, 0, 0)
        self.__viewport_layout.setSpacing(3)
        self.__viewport.setLayout(self.__viewport_layout)

        self.__listeners = core.ListenerMap[str]()

        self.__current_track = None  # type: music.Track
        self.__tracks = []  # type: List[base_track_editor.BaseTrackEditor]
        self.__track_map = {}  # type: Dict[int, base_track_editor.BaseTrackEditor]

        for node in self.project.nodes:
            self.__addNode(node)

        self.__listeners['project:nodes'] = self.project.nodes_changed.add(
            self.__onNodesChanged)

        for idx, track_editor in enumerate(self.__tracks):
            if idx == 0:
                self.__onCurrentTrackChanged(track_editor.track)

        self.currentTrackChanged.connect(self.__onCurrentTrackChanged)

        self.__player_state.currentTimeChanged.connect(
            lambda time: self.setPlaybackPos(time, 1))

    def cleanup(self) -> None:
        for track_editor in list(self.__tracks):
            self.__removeNode(track_editor.track)

        self.__listeners.cleanup()

    def currentTrack(self) -> music.Track:
        return self.__current_track

    def setCurrentTrack(self, track: music.Track) -> None:
        if track is self.__current_track:
            return

        if self.__current_track is not None:
            track_editor = self.__track_map[self.__current_track.id]
            track_editor.setIsCurrent(False)
            if self.__current_track.visible:
                self.update(
                    0, track_editor.y() - self.yOffset(),
                    self.width(), track_editor.height())
            self.__current_track = None

        if track is not None:
            track_editor = self.__track_map[track.id]
            track_editor.setIsCurrent(True)
            self.__current_track = track

            if self.__current_track.visible:
                self.update(
                    0, track_editor.y() - self.yOffset(),
                    self.width(), track_editor.height())

            if track_editor.track.visible and self.isVisible():
                yoffset = self.yOffset()
                if track_editor.y() + track_editor.height() > yoffset + self.height():
                    yoffset = track_editor.y() + track_editor.height() - self.height()
                if track_editor.y() < yoffset:
                    yoffset = track_editor.y()
                self.setYOffset(yoffset)

        self.currentTrackChanged.emit(self.__current_track)

    def __addNode(self, node: music.BaseNode) -> None:
        if isinstance(node, music.Track):
            track_editor = self.createTrack(node)
            self.__tracks.append(track_editor)
            self.__track_map[node.id] = track_editor
            self.__listeners['track:%s:visible' % node.id] = node.visible_changed.add(
                lambda *_: self.updateTracks())
            self.updateTracks()

    def __removeNode(self, node: music.BaseNode) -> None:
        if isinstance(node, music.Track):
            del self.__listeners['track:%s:visible' % node.id]

            track_editor = self.__track_map.pop(node.id)
            for idx in range(len(self.__tracks)):
                if self.__tracks[idx] is track_editor:
                    del self.__tracks[idx]
                    break

            track_editor.cleanup()
            self.updateTracks()

    def __onNodesChanged(
            self, change: music.PropertyListChange[music.BaseNode]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addNode(change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeNode(change.old_value)

        else:  # pragma: no cover
            raise TypeError(type(change))

    def createTrack(self, track: music.Track) -> base_track_editor.BaseTrackEditor:
        track_editor_cls = ui_registry.track_editor_cls_map[type(track).__name__]
        track_editor = track_editor_cls(
            track=track,
            player_state=self.__player_state,
            editor=self,
            context=self.context)
        self.xOffsetChanged.connect(track_editor.setXOffset)
        track_editor.setXOffset(self.xOffset())
        return track_editor

    def updateTracks(self) -> None:
        while self.__viewport_layout.count() > 0:
            self.__viewport_layout.takeAt(0)

        for track_editor in self.__tracks:
            track_editor.setVisible(track_editor.track.visible)
            if not track_editor.track.visible:
                continue
            self.__viewport_layout.addWidget(track_editor)

        self.__viewport.adjustSize()
        self.__viewport.resize(self.width(), self.__viewport.height())

        self.maximumYOffsetChanged.emit(
            max(0, self.__viewport.height() - self.height()))

        self.update()

    def __onCurrentTrackChanged(self, track: music.Track) -> None:
        if track is not None:
            track_editor = down_cast(base_track_editor.BaseTrackEditor, self.__track_map[track.id])
            self.__current_track_editor = track_editor

            self.setCurrentToolBoxClass(track_editor.toolBoxClass)

        else:
            self.__current_track_editor = None
            self.setCurrentToolBoxClass(None)

    def currentToolBox(self) -> tools.ToolBox:
        return self.__current_tool_box

    def setCurrentToolBoxClass(self, cls: Type[tools.ToolBox]) -> None:
        if type(self.__current_tool_box) is cls:  # pylint: disable=unidiomatic-typecheck
            return
        logger.debug("Switching to tool box class %s", cls)

        if self.__current_tool_box is not None:
            self.__current_tool_box.currentToolChanged.disconnect(self.__onCurrentToolChanged)
            self.__onCurrentToolChanged(None)
            self.__current_tool_box = None

        if cls is not None:
            self.__current_tool_box = cls(context=self.context)
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
        return max(0, self.__viewport.height() - self.height())

    def pageHeight(self) -> int:
        return self.height()

    def yOffset(self) -> int:
        return self.__y_offset

    def setYOffset(self, offset: int) -> None:
        if offset == self.__y_offset:
            return

        self.__y_offset = offset
        self.yOffsetChanged.emit(self.__y_offset)

        self.__viewport.move(0, -self.__y_offset)

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), self.__y_offset)

    def setPlaybackPos(self, current_time: audioproc.MusicalTime, num_samples: int) -> None:
        for track_editor in self.__tracks:
            track_editor.setPlaybackPos(current_time)

    def onClearSelection(self) -> None:
        if self.selection_set.empty():
            return

        with self.project.apply_mutations('Clear selection'):
            for mref in sorted(
                    (cast(measured_track_editor.MeasureEditor, measure_editor).measure_reference
                     for measure_editor in self.selection_set),
                    key=lambda mref: mref.index):
                mref.clear_measure()

    def onPaste(self, *, mode: str) -> None:
        assert mode in ('overwrite', 'link')

        if self.selection_set.empty():
            return

        clipboard = self.app.clipboardContent()
        if clipboard['type'] == 'measures':
            with self.project.apply_mutations('Paste measures'):
                self.project.paste_measures(
                    mode=mode,
                    src_objs=[copy['data'] for copy in clipboard['data']],
                    targets=sorted(
                        (cast(measured_track_editor.MeasureEditor, measure_editor).measure_reference
                         for measure_editor in self.selection_set),
                        key=lambda mref: mref.index))

        else:
            raise ValueError(clipboard['type'])

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.__viewport.resize(self.width(), self.__viewport.height())

        self.maximumYOffsetChanged.emit(
            max(0, self.__viewport.height() - self.height()))
        self.pageHeightChanged.emit(self.height())

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if evt.modifiers() == Qt.ShiftModifier:
            offset = self.xOffset()
            offset -= 2 * evt.angleDelta().y()
            offset = min(self.maximumXOffset(), offset)
            offset = max(0, offset)
            self.setXOffset(offset)
            evt.accept()
            return

        elif evt.modifiers() == Qt.NoModifier:
            offset = self.yOffset()
            offset -= evt.angleDelta().y()
            offset = min(self.maximumYOffset(), offset)
            offset = max(0, offset)
            self.setYOffset(offset)
            evt.accept()
            return

        super().wheelEvent(evt)

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_Left:
            if self.scaleX() > fractions.Fraction(10, 1):
                self.setScaleX(self.scaleX() * fractions.Fraction(2, 3))
            evt.accept()
            return

        if evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_Right:
            self.setScaleX(self.scaleX() * fractions.Fraction(3, 2))
            evt.accept()
            return

        super().keyPressEvent(evt)
