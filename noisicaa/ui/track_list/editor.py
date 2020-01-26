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
from typing import Any, List, Tuple

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
from . import tools

logger = logging.getLogger(__name__)


class TrackSeparator(QtWidgets.QWidget):
    def __init__(self, parent: 'Editor', container: 'TrackContainer') -> None:
        super().__init__(parent)

        if container is not None:
            self.setCursor(Qt.SizeVerCursor)

        self.__editor = parent
        self.__container = container
        self.__click_pos = None  # type: QtCore.QPoint

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__container is not None and evt.button() == Qt.LeftButton:
            self.__click_pos = evt.pos()
            self.__editor.beginTrackResize()
            evt.accept()

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__click_pos is not None:
            pos = self.mapTo(self.__editor, evt.pos() - self.__click_pos)

            self.__editor.setTrackHeight(
                self.__container, max(0, pos.y() - self.__container.track_editor.y()))

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


class TrackHandle(slots.SlotContainer, QtWidgets.QWidget):
    isCurrent, setIsCurrent, isCurrentChanged = slots.slot(bool, 'isCurrent', default=False)

    def __init__(self, *, editor: 'Editor', container: 'TrackContainer', **kwargs: Any) -> None:
        super().__init__(parent=editor, **kwargs)

        self.__editor = editor
        self.__container = container
        self.__click_pos = None  # type: QtCore.QPoint

        self.setCursor(Qt.OpenHandCursor)

        self.isCurrentChanged.connect(lambda _: self.update())

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__editor.setCurrentTrack(self.__container.track)

        if evt.button() == Qt.LeftButton:
            self.__click_pos = evt.pos()
            self.__editor.beginTrackMove(self.__container)
            self.setCursor(Qt.ClosedHandCursor)
            evt.accept()

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__click_pos is not None:
            mpos = self.mapTo(self.__editor, evt.pos()).y()
            if mpos < 20:
                self.__editor.setAutoScroll(-min(20, (20 - mpos) // 2))
            elif mpos > self.__editor.height() - 20:
                self.__editor.setAutoScroll(min(20, (mpos - self.__editor.height() + 20) // 2))
            else:
                self.__editor.setAutoScroll(0)
            pos = self.mapTo(self.__editor, evt.pos() - self.__click_pos)
            self.__editor.moveTrack(pos.y())
            evt.accept()

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__click_pos is not None:
            self.__click_pos = None
            self.__editor.endTrackMove()
            self.__editor.setAutoScroll(0)
            self.setCursor(Qt.OpenHandCursor)
            evt.accept()

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            w = self.width()
            h = self.height()

            if self.isCurrent():
                c_tl = QtGui.QColor(255, 255, 255)
                c_br = QtGui.QColor(160, 160, 255)
                c_body = QtGui.QColor(220, 220, 255)
            else:
                c_tl = QtGui.QColor(255, 255, 255)
                c_br = QtGui.QColor(160, 160, 160)
                c_body = QtGui.QColor(220, 220, 220)

            painter.fillRect(0, 0, w, 1, c_tl)
            painter.fillRect(0, 1, 1, h - 1, c_tl)
            painter.fillRect(1, h - 1, w - 1, 1, c_br)
            painter.fillRect(w - 1, 1, 1, h - 2, c_br)
            painter.fillRect(1, 1, w - 2, 1, c_tl)
            painter.fillRect(1, 2, 1, h - 3, c_tl)
            painter.fillRect(2, h - 2, w - 3, 1, c_br)
            painter.fillRect(w - 2, 2, 1, h - 4, c_br)
            painter.fillRect(2, 2, w - 4, h - 4, c_body)

            mx = w // 2
            my = h // 2

            for i in (0, -1, 1, -2, 2):
                hy1 = my - 3 + 8 * i
                hy2 = my + 3 + 8 * i

                if my - 8 * abs(i) >= 13:
                    painter.fillRect(mx - 2, hy1, 1, hy2 - hy1, c_br)
                    painter.fillRect(mx - 1, hy1, 1, hy2 - hy1 - 1, c_br)
                    painter.fillRect(mx - 1, hy2 - 1, 1, 1, c_tl)
                    painter.fillRect(mx, hy1, 1, 1, c_br)
                    painter.fillRect(mx, hy1 + 1, 1, hy2 - hy1 - 1, c_tl)
                    painter.fillRect(mx + 1, hy1, 1, hy2 - hy1, c_tl)

        finally:
            painter.end()


class TrackLabel(slots.SlotContainer, QtWidgets.QLabel):
    isCurrent, setIsCurrent, isCurrentChanged = slots.slot(bool, 'isCurrent', default=False)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent=parent)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setBackgroundRole(QtGui.QPalette.Window)
        self.setAutoFillBackground(True)

        self.isCurrentChanged.connect(
            lambda current: self.setBackgroundRole(
                QtGui.QPalette.Highlight if current else QtGui.QPalette.Window))

        font = QtGui.QFont(self.font())
        font.setPointSizeF(0.8 * font.pointSizeF())
        self.setFont(font)


class TrackContainer(
        object_list_manager.ObjectWrapper[music.Track, 'Editor'],
        ui_base.ProjectMixin,
        QtCore.QObject):
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(
            self, *,
            editor: 'Editor',
            track: music.Track,
            player_state: player_state_lib.PlayerState,
            **kwargs: Any) -> None:
        super().__init__(
            object_list_manager=editor,
            wrapped_object=track,
            **kwargs)

        self.editor = editor
        self.track = track

        self.__listeners = core.ListenerMap[str]()

        track_editor_cls = ui_registry.track_editor_cls_map[type(track).__name__]
        self.track_editor = track_editor_cls(
            track=track,
            player_state=player_state,
            editor=self.editor,
            context=self.editor.context)
        self.editor.xOffsetChanged.connect(self.track_editor.setXOffset)
        self.editor.scaleXChanged.connect(self.track_editor.setScaleX)
        self.editor.zoomChanged.connect(self.track_editor.setZoom)
        self.editor.playbackPositionChanged.connect(self.track_editor.setPlaybackPosition)
        self.track_editor.setXOffset(self.editor.xOffset())

        self.__listeners['visible'] = self.track.visible_changed.add(
            lambda change: self.visibilityChanged.emit(change.new_value))

        self.height = self.editor.get_session_value(
            'track_editor:%016x:height' % self.track.id,
            fractions.Fraction(self.track_editor.defaultHeight()))

        self.top_separator = TrackSeparator(editor, None)
        self.separator = TrackSeparator(editor, self)
        self.label = TrackLabel(editor)
        self.label.setText(self.track.name)
        self.__listeners['name'] = self.track.name_changed.add(
            lambda change: self.label.setText(change.new_value))

        self.handle = TrackHandle(editor=editor, container=self)

        self.__hide_label_under_mouse = False
        self.__hide_label_small_track = False
        self.__global_mouse_move_conn = self.app.globalMousePosChanged.connect(
            self.__globalMouseMove)

    def cleanup(self) -> None:
        self.__listeners.cleanup()

        self.app.globalMousePosChanged.disconnect(self.__global_mouse_move_conn)

        self.track_editor.hide()
        self.track_editor.cleanup()

        self.separator.setParent(None)
        self.separator.hide()

        self.handle.setParent(None)
        self.handle.hide()

        self.label.setParent(None)
        self.label.hide()

    def __globalMouseMove(self, pos: QtCore.QPoint) -> None:
        pos = self.label.mapFromGlobal(pos)
        rect = self.label.rect().adjusted(-10, -10, 10, 10)
        self.__hide_label_under_mouse = rect.contains(pos)
        self.label.setVisible(
            not self.__hide_label_under_mouse and not self.__hide_label_small_track)

    def setTrackGeometry(
            self, rect: QtCore.QRect, sidebar_width: int, separator_height: int, show_top_sep: bool
    ) -> None:
        handle_width = 12

        if show_top_sep:
            self.top_separator.setVisible(True)
            self.top_separator.setGeometry(
                rect.x(), rect.y() - separator_height, rect.width(), separator_height)
        else:
            self.top_separator.setVisible(False)

        self.handle.setVisible(True)
        self.handle.setGeometry(rect.x(), rect.y(), handle_width, rect.height())

        self.track_editor.setVisible(True)
        self.track_editor.setGeometry(
            rect.x() + handle_width, rect.y(), rect.width() - handle_width, rect.height())

        self.__hide_label_small_track = (rect.height() < self.label.height() + 4)
        self.label.move(rect.x() + handle_width + 4, rect.y() + 2)
        self.label.setVisible(
            not self.__hide_label_under_mouse and not self.__hide_label_small_track)

        self.separator.setVisible(True)
        self.separator.setGeometry(
            rect.x(), rect.y() + rect.height(), rect.width(), separator_height)

    def hide(self) -> None:
        self.handle.setVisible(False)
        self.track_editor.setVisible(False)
        self.label.setVisible(False)
        self.top_separator.setVisible(False)
        self.separator.setVisible(False)

    def setIsCurrent(self, is_current: bool) -> None:
        self.handle.setIsCurrent(is_current)
        self.track_editor.setIsCurrent(is_current)
        self.label.setIsCurrent(is_current)

    def setHeight(self, height: fractions.Fraction) -> None:
        self.height = height
        self.editor.set_session_value('track_editor:%016x:height' % self.track.id, height)

    def raise_(self) -> None:
        self.handle.raise_()
        self.track_editor.raise_()
        self.label.raise_()
        self.top_separator.raise_()
        self.separator.raise_()


class Editor(
        object_list_manager.ObjectListManager[music.Track, TrackContainer],
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

        self.__in_track_resize = False
        self.__moving_track = None  # type: TrackContainer
        self.__moving_track_pos = None  # type: int
        self.__moving_track_insert_index = None  # type: int

        self.__auto_scroll_dy = 0
        self.__auto_scroll_timer = QtCore.QTimer(self)
        self.__auto_scroll_timer.setInterval(1000 // 50)
        self.__auto_scroll_timer.timeout.connect(self.__autoScrollTick)

        self.initObjectList(self.project, 'nodes')

        self.__content_height = 0
        self.__updateTracks()
        self.objectListChanged.connect(self.__updateTracks)

        self.sidebarWidthChanged.connect(self.__updateTracks)

        self.__current_track = None  # type: music.Track
        for idx, container in enumerate(self.objectWrappers()):
            if idx == 0:
                self.__onCurrentTrackChanged(container.track)
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

    def __autoScrollTick(self) -> None:
        self.setYOffset(
            max(0, min(self.maximumYOffset(), self.yOffset() + self.__auto_scroll_dy)))

    def setAutoScroll(self, dy: int) -> None:
        self.__auto_scroll_dy = dy
        if self.__auto_scroll_dy and self.isVisible():
            self.__auto_scroll_timer.start()
        else:
            self.__auto_scroll_timer.stop()

    def currentTrack(self) -> music.Track:
        return self.__current_track

    def setCurrentTrack(self, track: music.Track) -> None:
        if track is self.__current_track:
            return

        if self.__current_track is not None:
            container = self.objectWrapperById(self.__current_track.id)
            container.setIsCurrent(False)
            self.__current_track = None

        if track is not None:
            container = self.objectWrapperById(track.id)
            container.setIsCurrent(True)
            self.__current_track = track

            if container.track.visible and self.isVisible():
                track_y = container.track_editor.y() + self.yOffset()
                yoffset = self.yOffset()
                if track_y + container.track_editor.height() > yoffset + self.height():
                    yoffset = track_y + container.track_editor.height() - self.height()
                if track_y < yoffset:
                    yoffset = track_y
                self.setYOffset(yoffset)

        self.currentTrackChanged.emit(self.__current_track)

    def _filterObject(self, obj: music.ObjectBase) -> bool:
        return isinstance(obj, music.Track)

    def _createObjectWrapper(self, track: music.Track) -> TrackContainer:
        container = TrackContainer(
            editor=self,
            track=track,
            player_state=self.__player_state,
            context=self.context)
        container.visibilityChanged.connect(lambda _: self.__updateTracks())
        return container

    def _deleteObjectWrapper(self, container: TrackContainer) -> None:
        if container.track is self.__current_track:
            self.setCurrentTrack(None)

        container.cleanup()

    def __updateTracks(self) -> None:
        separator_height = max(1, min(8, int(self.zoom() * 4)))
        tracks = []  # type: List[Tuple[TrackContainer, int]]
        moving_track_height = 0

        content_height = 0
        for container in self.objectWrappers():
            if not container.track.visible:
                container.hide()
                continue

            if not tracks:
                content_height += separator_height

            track_height = max(5, int(self.zoom() * container.height))
            track_height = min(container.track_editor.maximumHeight(), track_height)
            track_height = max(container.track_editor.minimumHeight(), track_height)

            if container is self.__moving_track:
                moving_track_height = track_height

            tracks.append((container, track_height))

            content_height += track_height + separator_height

        if self.__in_track_resize:
            content_height = max(content_height, self.__content_height)

        if content_height != self.__content_height:
            self.__content_height = content_height
            self.maximumYOffsetChanged.emit(max(0, self.__content_height - self.height()))

        if self.__content_height >= self.height():
            y = -self.yOffset()
        else:
            y = (self.height() - self.__content_height) // 2
        y += separator_height

        show_top_sep = True
        moving_track_inserted = False
        for container, track_height in tracks:
            if container is self.__moving_track:
                container.setTrackGeometry(
                    QtCore.QRect(0, self.__moving_track_pos, self.width(), track_height),
                    self.sidebarWidth(), separator_height, True)
                show_top_sep = True

            else:
                if (not moving_track_inserted
                        and self.__moving_track is not None
                        and self.__moving_track_pos < y + track_height // 2):
                    y += moving_track_height + separator_height
                    if container.track.index > self.__moving_track.track.index:
                        self.__moving_track_insert_index = container.track.index - 1
                    else:
                        self.__moving_track_insert_index = container.track.index
                    moving_track_inserted = True

                container.setTrackGeometry(
                    QtCore.QRect(0, y, self.width(), track_height),
                    self.sidebarWidth(), separator_height, show_top_sep)
                show_top_sep = False

                y += track_height + separator_height

        if not moving_track_inserted and self.__moving_track is not None:
            self.__moving_track_insert_index = len(self.project.nodes) - 1

        if self.__moving_track is not None:
            self.__moving_track.raise_()

    def beginTrackResize(self) -> None:
        self.__in_track_resize = True

    def endTrackResize(self) -> None:
        self.__in_track_resize = False
        self.__updateTracks()

    def setTrackHeight(self, container: TrackContainer, height: int) -> None:
        h = fractions.Fraction(height) / self.zoom()
        h = min(container.track_editor.maximumHeight(), h)
        h = max(container.track_editor.minimumHeight(), h)
        if h != container.height:
            container.setHeight(h)
            self.__updateTracks()

    def beginTrackMove(self, container: TrackContainer) -> None:
        self.__moving_track = container
        self.__moving_track_pos = container.track_editor.pos().y()
        self.__moving_track_insert_index = None
        self.__updateTracks()

    def endTrackMove(self) -> None:
        assert self.__moving_track is not None
        if self.__moving_track_insert_index is not None:
            moving_track = self.__moving_track
            new_index = self.__moving_track_insert_index
            self.__moving_track = None
            self.__moving_track_insert_index = None
            with self.project.apply_mutations(
                    'Move track "%s"' % moving_track.track.name):
                self.project.nodes.move(moving_track.track.index, new_index)

        self.__updateTracks()

    def moveTrack(self, pos: int) -> None:
        self.__moving_track_pos = pos
        self.__updateTracks()

    def __onCurrentTrackChanged(self, track: music.Track) -> None:
        if track is not None:
            container = self.objectWrapperById(track.id)
            self.setCurrentToolBox(container.track_editor.toolBox())

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
