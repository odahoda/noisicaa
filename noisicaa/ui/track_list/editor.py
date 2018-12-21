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

import fractions
import logging
from typing import cast, Any, Optional, Union, Sequence, Dict, List, Tuple, Type  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core  # pylint: disable=unused-import
from noisicaa import music
from noisicaa import model
from noisicaa.ui import ui_base
from noisicaa.ui import player_state as player_state_lib
from . import time_view_mixin
from . import base_track_editor
from . import measured_track_editor
from . import beat_track_editor
from . import control_track_editor
from . import score_track_editor
from . import sample_track_editor
from . import tools

logger = logging.getLogger(__name__)

track_editor_map = {
    'ScoreTrack': score_track_editor.ScoreTrackEditor,
    'BeatTrack': beat_track_editor.BeatTrackEditor,
    'ControlTrack': control_track_editor.ControlTrackEditor,
    'SampleTrack': sample_track_editor.SampleTrackEditor,
}  # type: Dict[str, Type[base_track_editor.BaseTrackEditor]]


class AsyncSetupBase(object):
    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass


class Editor(
        time_view_mixin.TimeViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, *, player_state: player_state_lib.PlayerState, **kwargs: Any) -> None:
        self.__player_state = player_state

        self.__current_tool_box = None  # type: tools.ToolBox
        self.__current_tool = None  # type: tools.ToolBase
        self.__mouse_grabber = None  # type: base_track_editor.BaseTrackEditor
        self.__current_track_editor = None  # type: base_track_editor.BaseTrackEditor
        self.__hover_track_editor = None  # type: base_track_editor.BaseTrackEditor

        self.__y_offset = 0
        self.__content_height = 100

        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(0)

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.__current_track = None  # type: music.Track
        self.__tracks = []  # type: List[base_track_editor.BaseTrackEditor]
        self.__track_map = {}  # type: Dict[int, base_track_editor.BaseTrackEditor]

        for node in self.project.pipeline_graph_nodes:
            self.__addNode(node)

        self.__listeners['project:nodes'] = self.project.pipeline_graph_nodes_changed.add(
            self.__onNodesChanged)

        for idx, track_editor in enumerate(self.__tracks):
            if idx == 0:
                self.__onCurrentTrackChanged(track_editor.track)

        self.updateTracks()
        self.currentTrackChanged.connect(self.__onCurrentTrackChanged)

        self.__player_state.currentTimeChanged.connect(
            lambda time: self.setPlaybackPos(time, 1))

        self.scaleXChanged.connect(lambda _: self.updateTracks())

    async def setup(self) -> None:
        await super().setup()

    async def cleanup(self) -> None:
        for track_editor in list(self.__tracks):
            self.__removeNode(track_editor.track)

        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        await super().cleanup()

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
                    0, track_editor.viewTop() - self.yOffset(),
                    self.width(), track_editor.height())
            self.__current_track = None

        if track is not None:
            track_editor = self.__track_map[track.id]
            track_editor.setIsCurrent(True)
            self.__current_track = track

            if self.__current_track.visible:
                self.update(
                    0, track_editor.viewTop() - self.yOffset(),
                    self.width(), track_editor.height())

            if track_editor.track.visible and self.isVisible():
                yoffset = self.yOffset()
                if track_editor.viewTop() + track_editor.height() > yoffset + self.height():
                    yoffset = track_editor.viewTop() + track_editor.height() - self.height()
                if track_editor.viewTop() < yoffset:
                    yoffset = track_editor.viewTop()
                self.setYOffset(yoffset)

        self.currentTrackChanged.emit(self.__current_track)

    def __addNode(self, node: music.BasePipelineGraphNode) -> None:
        if isinstance(node, music.Track):
            track_editor = self.createTrack(node)
            self.__tracks.append(track_editor)
            self.__track_map[node.id] = track_editor
            self.__listeners['track:%s:visible' % node.id] = node.visible_changed.add(
                lambda *_: self.updateTracks())
            self.updateTracks()

    def __removeNode(self, node: music.BasePipelineGraphNode) -> None:
        if isinstance(node, music.Track):
            self.__listeners.pop('track:%s:visible' % node.id).remove()

            track_editor = self.__track_map.pop(node.id)
            for idx in range(len(self.__tracks)):
                if self.__tracks[idx] is track_editor:
                    del self.__tracks[idx]
                    break

            track_editor.close()
            self.updateTracks()

    def __onNodesChanged(
            self, change: model.PropertyListChange[music.BasePipelineGraphNode]) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.__addNode(change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.__removeNode(change.old_value)

        else:  # pragma: no cover
            raise TypeError(type(change))

    def createTrack(self, track: music.Track) -> base_track_editor.BaseTrackEditor:
        track_editor_cls = track_editor_map[type(track).__name__]
        track_editor = track_editor_cls(
            track=track,
            player_state=self.__player_state,
            editor=self,
            context=self.context)
        track_editor.rectChanged.connect(
            lambda rect: self.update(rect.translated(-self.offset())))
        track_editor.sizeChanged.connect(
            lambda size: self.updateTracks())
        return track_editor

    def updateTracks(self) -> None:
        self.__content_height = 0

        p = QtCore.QPoint(0, 0)
        for track_editor in self.__tracks:
            if not track_editor.track.visible:
                continue

            track_editor.setScaleX(self.scaleX())
            track_editor.setViewTopLeft(p)
            p += QtCore.QPoint(0, track_editor.height())
            p += QtCore.QPoint(0, 3)

        self.__content_height = p.y() + 10

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))

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
        return max(0, self.__content_height - self.height())

    def pageHeight(self) -> int:
        return self.height()

    def yOffset(self) -> int:
        return self.__y_offset

    def setYOffset(self, offset: int) -> None:
        if offset == self.__y_offset:
            return

        dy = self.__y_offset - offset
        self.__y_offset = offset
        self.yOffsetChanged.emit(self.__y_offset)

        self.scroll(0, dy)

    def offset(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.xOffset(), self.__y_offset)

    def setPlaybackPos(self, current_time: audioproc.MusicalTime, num_samples: int) -> None:
        for track_editor in self.__tracks:
            track_editor.setPlaybackPos(current_time)

    def onClearSelection(self) -> None:
        if self.selection_set.empty():
            return

        self.send_command_async(music.Command(
            target=self.project.id,
            clear_measures=music.ClearMeasures(
                measure_ids=[
                    mref.id for mref in sorted(
                        (cast(measured_track_editor.MeasureEditor, measure_editor).measure_reference
                         for measure_editor in self.selection_set),
                        key=lambda mref: mref.index)])))

    def onPaste(self, *, mode: str) -> None:
        assert mode in ('overwrite', 'link')

        if self.selection_set.empty():
            return

        clipboard = self.app.clipboardContent()
        if clipboard['type'] == 'measures':
            target_ids = [
                mref.id for mref in sorted(
                    (cast(measured_track_editor.MeasureEditor, measure_editor).measure_reference
                     for measure_editor in self.selection_set),
                    key=lambda mref: mref.index)]

            self.send_command_async(music.Command(
                target=self.project.id,
                paste_measures=music.PasteMeasures(
                    mode=mode,
                    src_objs=[copy['data'] for copy in clipboard['data']],
                    target_ids=target_ids)))

        else:
            raise ValueError(clipboard['type'])

    def trackEditorAt(self, pos: QtCore.QPoint) -> base_track_editor.BaseTrackEditor:
        p = -self.offset()
        for track_editor in self.__tracks:
            if not track_editor.track.visible:
                continue

            if p.y() <= pos.y() < p.y() + track_editor.height():
                return down_cast(base_track_editor.BaseTrackEditor, track_editor)

            p += QtCore.QPoint(0, track_editor.height())
            p += QtCore.QPoint(0, 3)

        return None

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.height())

    def setHoverTrackEditor(
            self, track_editor: Optional[base_track_editor.BaseTrackEditor],
            evt: Union[None, QtGui.QEnterEvent, QtGui.QMouseEvent]
    ) -> None:
        if track_editor is self.__hover_track_editor:
            return

        if self.__hover_track_editor is not None:
            track_evt = QtCore.QEvent(QtCore.QEvent.Leave)
            self.__hover_track_editor.leaveEvent(track_evt)

        if track_editor is not None:
            track_evt = QtGui.QEnterEvent(
                evt.localPos() + self.offset() - track_editor.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos())
            track_editor.enterEvent(track_evt)

        self.__hover_track_editor = track_editor

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        evt = down_cast(QtGui.QEnterEvent, evt)
        self.setHoverTrackEditor(self.trackEditorAt(evt.pos()), evt)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverTrackEditor(None, None)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__mouse_grabber is not None:
            track_editor = self.__mouse_grabber
        else:
            track_editor = self.trackEditorAt(evt.pos())
            self.setHoverTrackEditor(track_editor, evt)

        if track_editor is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_editor.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_evt.setAccepted(False)
            track_editor.mouseMoveEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        track_editor = self.trackEditorAt(evt.pos())
        if track_editor is not None:
            if not track_editor.isCurrent():
                self.setCurrentTrack(track_editor.track)
                evt.accept()
                return

        if track_editor is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_editor.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_evt.setAccepted(False)
            track_editor.mousePressEvent(track_evt)
            if track_evt.isAccepted():
                self.__mouse_grabber = track_editor
            evt.setAccepted(track_evt.isAccepted())
            return

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__mouse_grabber is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - self.__mouse_grabber.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_evt.setAccepted(False)
            self.__mouse_grabber.mouseReleaseEvent(track_evt)
            self.__mouse_grabber = None
            evt.setAccepted(track_evt.isAccepted())
            self.setHoverTrackEditor(self.trackEditorAt(evt.pos()), evt)
            return

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        track_editor = self.trackEditorAt(evt.pos())
        if track_editor is not None:
            if not track_editor.isCurrent():
                self.setCurrentTrack(track_editor.track)
                evt.accept()
                return

        if track_editor is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_editor.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_evt.setAccepted(False)
            track_editor.mouseDoubleClickEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

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

        track_editor = self.trackEditorAt(evt.pos())
        if track_editor is not None:
            track_evt = QtGui.QWheelEvent(
                evt.pos() + self.offset() - track_editor.viewTopLeft(),
                evt.globalPos(),
                evt.pixelDelta(),
                evt.angleDelta(),
                0,
                Qt.Horizontal,
                evt.buttons(),
                evt.modifiers(),
                evt.phase(),
                evt.source())
            track_evt.setAccepted(False)
            track_editor.wheelEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

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

        current_track = self.currentTrack()
        if current_track is not None:
            current_track_editor = self.__track_map[current_track.id]
            track_evt = QtGui.QKeyEvent(
                evt.type(),
                evt.key(),
                evt.modifiers(),
                evt.nativeScanCode(),
                evt.nativeVirtualKey(),
                evt.nativeModifiers(),
                evt.text(),
                evt.isAutoRepeat(),
                evt.count())
            track_evt.setAccepted(False)
            current_track_editor.keyPressEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        current_track = self.currentTrack()
        if current_track is not None:
            current_track_editor = self.__track_map[current_track.id]
            track_evt = QtGui.QKeyEvent(
                evt.type(),
                evt.key(),
                evt.modifiers(),
                evt.nativeScanCode(),
                evt.nativeVirtualKey(),
                evt.nativeModifiers(),
                evt.text(),
                evt.isAutoRepeat(),
                evt.count())
            track_evt.setAccepted(False)
            current_track_editor.keyReleaseEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        track_editor = self.trackEditorAt(evt.pos())
        if track_editor is not None:
            menu = QtWidgets.QMenu()
            track_editor.buildContextMenu(
                menu, evt.pos() + self.offset() - track_editor.viewTopLeft())
            if not menu.isEmpty():
                menu.exec_(evt.globalPos())
                evt.accept()
                return

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        super().paintEvent(evt)

        #t1 = time.perf_counter()

        painter = QtGui.QPainter(self)
        try:
            p = -self.offset()
            for track_editor in self.__tracks:
                if not track_editor.track.visible:
                    continue

                track_rect = QtCore.QRect(
                    0, p.y(), max(self.contentWidth(), self.width()), track_editor.height())
                track_rect = track_rect.intersected(evt.rect())
                if not track_rect.isEmpty():
                    painter.save()
                    try:
                        painter.setClipRect(track_rect)
                        painter.translate(p)
                        track_editor.paint(painter, track_rect.translated(-p))
                    finally:
                        painter.restore()

                # TODO: messes up display, when scrolling horizontally.
                #painter.drawText(15, p.y() + 14, track_editor.track.name)

                p += QtCore.QPoint(0, track_editor.height())

                painter.fillRect(
                    evt.rect().left(), p.y(),
                    evt.rect().width(), 3,
                    QtGui.QColor(200, 200, 200))
                p += QtCore.QPoint(0, 3)

            fill_rect = QtCore.QRect(p, evt.rect().bottomRight())
            if not fill_rect.isEmpty():
                painter.fillRect(fill_rect, Qt.white)

        finally:
            painter.end()

        #t2 = time.perf_counter()

        #logger.info("Editor.paintEvent(%s): %.2fµs", evt.rect(), 1e6 * (t2 - t1))
