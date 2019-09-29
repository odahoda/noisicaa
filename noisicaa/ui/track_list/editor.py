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
from typing import Any, Dict, List, Tuple

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


class TrackSeparator(QtWidgets.QWidget):
    def __init__(self, parent: 'Editor', track_editor: base_track_editor.BaseTrackEditor) -> None:
        super().__init__(parent)

        if track_editor is not None:
            self.setCursor(Qt.SizeVerCursor)

        self.__editor = parent
        self.__track_editor = track_editor
        self.__click_pos = None  # type: QtCore.QPoint

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__track_editor is not None and evt.button() == Qt.LeftButton:
            self.__click_pos = evt.pos()
            self.__editor.beginTrackResize()
            evt.accept()

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__click_pos is not None:
            pos = self.mapTo(self.__editor, evt.pos() - self.__click_pos)

            self.__editor.setTrackHeight(
                self.__track_editor, max(0, pos.y() - self.__track_editor.y()))

            evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__click_pos is not None:
            self.__click_pos = None
            self.__editor.endTrackResize()
            evt.accept()

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            if self.height() >= 3:
                painter.fillRect(0, 0, self.width(), 1, QtGui.QColor(200, 200, 200))
                painter.fillRect(0, 1, self.width(), self.height() - 2, QtGui.QColor(100, 100, 100))
                painter.fillRect(0, self.height() - 1, self.width(), 1, QtGui.QColor(200, 200, 200))
            else:
                painter.fillRect(0, 0, self.width(), self.height(), QtGui.QColor(100, 100, 100))


        finally:
            painter.end()


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
    sidebarWidth, setSidebarWidth, sidebarWidthChanged = slots.slot(
        int, 'sidebarWidth', default=0)
    zoom, setZoom, zoomChanged = slots.slot(
        fractions.Fraction, 'zoom', default=fractions.Fraction(1, 1))

    MIN_ZOOM = fractions.Fraction(2, 3) ** 12
    MAX_ZOOM = fractions.Fraction(3, 2) ** 2

    def __init__(self, *, player_state: player_state_lib.PlayerState, **kwargs: Any) -> None:
        self.__player_state = player_state

        self.__current_tool_box = None  # type: tools.ToolBox
        self.__current_tool = None  # type: tools.ToolBase
        self.__y_offset = 0

        super().__init__(**kwargs)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(50)
        self.setMinimumHeight(0)

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__top_edge = TrackSeparator(self, None)
        self.__separators = {}  # type: Dict[int, TrackSeparator]
        self.__track_heights = {}  # type: Dict[int, fractions.Fraction]
        self.__in_track_resize = False

        self.initObjectList(self.project, 'nodes')

        self.__content_height = 0
        self.__updateTracks()
        self.objectListChanged.connect(self.__updateTracks)

        self.sidebarWidthChanged.connect(self.__updateTracks)

        self.__current_track = None  # type: music.Track
        for idx, track_editor in enumerate(self.objectWrappers()):
            if idx == 0:
                self.__onCurrentTrackChanged(track_editor.track)
        self.currentTrackChanged.connect(self.__onCurrentTrackChanged)

        self.__player_state.currentTimeChanged.connect(self.setPlaybackPosition)

        self.setZoom(self.get_session_value(
            'tracklist:%s:zoom' % self.project.id, fractions.Fraction(1, 1)))
        self.zoomChanged.connect(functools.partial(
            self.set_session_value, 'tracklist:%s:zoom' % self.project.id))
        self.zoomChanged.connect(lambda _: self.__updateTracks())

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

        self.__increase_zoom_action = QtWidgets.QAction(self)
        self.__increase_zoom_action.setShortcut("ctrl++")
        self.__increase_zoom_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__increase_zoom_action.triggered.connect(
            functools.partial(self.__scaleZoom, fractions.Fraction(3, 2)))
        self.addAction(self.__increase_zoom_action)

        self.__decrease_zoom_action = QtWidgets.QAction(self)
        self.__decrease_zoom_action.setShortcut("ctrl+-")
        self.__decrease_zoom_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__decrease_zoom_action.triggered.connect(
            functools.partial(self.__scaleZoom, fractions.Fraction(2, 3)))
        self.addAction(self.__decrease_zoom_action)

        self.__reset_zoom_action = QtWidgets.QAction(self)
        self.__reset_zoom_action.setShortcut("ctrl+0")
        self.__reset_zoom_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__reset_zoom_action.triggered.connect(self.__resetZoom)
        self.addAction(self.__reset_zoom_action)

    def __setScaleX(self, factor: fractions.Fraction) -> None:
        new_scale_x = self.scaleX() * factor
        new_scale_x = max(fractions.Fraction(5, 1), new_scale_x)
        new_scale_x = min(fractions.Fraction(10000, 1), new_scale_x)

        center_time = max(0, self.width() // 2 - self.leftMargin() + self.xOffset()) / self.scaleX()

        self.setScaleX(new_scale_x)

        center_x = self.leftMargin() + int(self.scaleX() * center_time)
        self.setXOffset(max(0, center_x - self.width() // 2))

    def __setZoom(self, zoom: fractions.Fraction) -> None:
        if zoom == self.zoom():
            return

        center_y = (self.yOffset() + self.height() // 2) / self.zoom()
        self.setZoom(zoom)
        self.setYOffset(
            max(0, min(self.maximumYOffset(), int(center_y * self.zoom()) - self.height() // 2)))

    def __scaleZoom(self, factor: fractions.Fraction) -> None:
        new_zoom = self.zoom() * factor
        new_zoom = max(self.MIN_ZOOM, new_zoom)
        new_zoom = min(self.MAX_ZOOM, new_zoom)
        self.__setZoom(new_zoom)
        self.__setScaleX(factor)

    def __resetZoom(self) -> None:
        self.__setScaleX(1 / self.zoom())
        self.__setZoom(fractions.Fraction(1, 1))

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
            track=track,
            player_state=self.__player_state,
            editor=self,
            context=self.context)
        self.xOffsetChanged.connect(track_editor.setXOffset)
        self.scaleXChanged.connect(track_editor.setScaleX)
        self.zoomChanged.connect(track_editor.setZoom)
        self.playbackPositionChanged.connect(track_editor.setPlaybackPosition)
        track_editor.setXOffset(self.xOffset())

        self.__listeners['track:%s:visible' % track.id] = track.visible_changed.add(
            lambda *_: self.__updateTracks())

        self.__separators[track.id] = TrackSeparator(self, track_editor)
        self.__track_heights[track.id] = self.get_session_value(
            'track_editor:%016x:height' % track.id,
            fractions.Fraction(track_editor.defaultHeight()))

        return track_editor

    def _deleteObjectWrapper(self, track_editor: base_track_editor.BaseTrackEditor) -> None:
        if track_editor.track is self.__current_track:
            self.setCurrentTrack(None)
        track_editor.hide()
        track_editor.cleanup()
        del self.__listeners['track:%s:visible' % track_editor.track.id]

        separator = self.__separators.pop(track_editor.track.id)
        separator.setParent(None)
        separator.hide()

        del self.__track_heights[track_editor.track.id]

    def __updateTracks(self) -> None:
        x = self.sidebarWidth()
        y = 0
        separator_height = max(1, min(8, int(self.zoom() * 4)))

        tracks = []  # type: List[Tuple[base_track_editor.BaseTrackEditor, QtCore.QRect]]
        for track_editor in self.objectWrappers():
            track_editor.setVisible(track_editor.track.visible)
            self.__separators[track_editor.track.id].setVisible(track_editor.track.visible)
            if not track_editor.track.visible:
                continue

            if not tracks:
                y += separator_height

            track_height = max(5, int(self.zoom() * self.__track_heights[track_editor.track.id]))
            track_height = min(track_editor.maximumHeight(), track_height)
            track_height = max(track_editor.minimumHeight(), track_height)
            tracks.append((track_editor, QtCore.QRect(x, y, self.width() - x, track_height)))
            y += track_height
            y += separator_height

        if self.__in_track_resize:
            y = max(y, self.__content_height)

        if y != self.__content_height:
            self.__content_height = y
            self.maximumYOffsetChanged.emit(max(0, self.__content_height - self.height()))

        if self.__content_height >= self.height():
            offset = QtCore.QPoint(0, -self.yOffset())
        else:
            offset = QtCore.QPoint(0, (self.height() - self.__content_height) // 2)

        if tracks:
            self.__top_edge.setVisible(True)
            self.__top_edge.setGeometry(0, offset.y(), self.width(), separator_height)
        else:
            self.__top_edge.setVisible(False)

        for track_editor, rect in tracks:
            rect = rect.translated(offset)
            track_editor.setGeometry(rect)
            separator = self.__separators[track_editor.track.id]
            separator.setGeometry(0, rect.y() + rect.height(), self.width(), separator_height)

        self.update()

    def beginTrackResize(self) -> None:
        self.__in_track_resize = True

    def endTrackResize(self) -> None:
        self.__in_track_resize = False
        self.__updateTracks()

    def setTrackHeight(self, track_editor: base_track_editor.BaseTrackEditor, height: int) -> None:
        h = fractions.Fraction(height) / self.zoom()
        h = min(track_editor.maximumHeight(), h)
        h = max(track_editor.minimumHeight(), h)

        if height != self.__track_heights[track_editor.track.id]:
            self.__track_heights[track_editor.track.id] = h
            self.set_session_value('track_editor:%016x:height' % track_editor.track.id, h)
            self.__updateTracks()

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

        self.__updateTracks()

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), self.__y_offset)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            if self.sidebarWidth() > 0:
                y = -self.yOffset()
                for track_editor in self.objectWrappers():
                    if not track_editor.isVisible():
                        continue

                    painter.fillRect(0, y, self.sidebarWidth(), track_editor.height(), Qt.red)
                    y += track_editor.height()

                    separator = self.__separators[track_editor.track.id]
                    y += separator.height()

        finally:
            painter.end()

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.height())

        self.__updateTracks()

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
