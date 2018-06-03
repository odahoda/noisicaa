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
import functools
import logging
import time as time_lib
import uuid
from typing import cast, Any, Optional, Union, Sequence, Dict, List, Tuple, Type  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa.audioproc.public import musical_time_pb2
from noisicaa import core  # pylint: disable=unused-import
from noisicaa import node_db
from noisicaa import music
from noisicaa import model
from . import dock_widget  # pylint: disable=unused-import
from . import project_properties_dock
from . import tracks_dock
from . import track_properties_dock
from . import pipeline_graph_view
from . import tool_dock
from . import ui_base
from . import tools
from . import render_dialog
from . import selection_set
from . import project_registry
from .track_items import base_track_item
from .track_items import score_track_item
from .track_items import beat_track_item
from .track_items import control_track_item
from .track_items import sample_track_item

logger = logging.getLogger(__name__)


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

        self.__playing = False
        self.__current_time = self.__get_session_value('current_time', audioproc.MusicalTime())
        self.__loop_start_time = self.__get_session_value('loop_start_time', None)
        self.__loop_end_time = self.__get_session_value('loop_end_time', None)
        self.__loop_enabled = self.__get_session_value('loop_enabled', False)

        self.__player_id = None  # type: str

    def __get_session_value(self, key: str, default: Any) -> Any:
        return self.get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key: str, value: Any) -> None:
        self.set_session_value(self.__session_prefix + key, value)

    def playerID(self) -> str:
        return self.__player_id

    def setPlayerID(self, player_id: str) -> None:
        self.__player_id = player_id

    def updateFromProto(self, player_state: audioproc.PlayerState) -> None:
        if player_state.HasField('current_time'):
            self.setCurrentTime(audioproc.MusicalTime.from_proto(player_state.current_time))

        if player_state.HasField('playing'):
            self.setPlaying(player_state.playing)

        if player_state.HasField('loop_enabled'):
            self.setLoopEnabled(player_state.loop_enabled)

        if player_state.HasField('loop_start_time'):
            self.setLoopStartTime(audioproc.MusicalTime.from_proto(player_state.loop_start_time))

        if player_state.HasField('loop_end_time'):
            self.setLoopEndTime(audioproc.MusicalTime.from_proto(player_state.loop_end_time))

    def setPlaying(self, playing: bool) -> None:
        if playing == self.__playing:
            return

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

        self.__loop_enabled = loop_enabled
        self.__set_session_value('loop_enabled', loop_enabled)
        self.loopEnabledChanged.emit(loop_enabled)

    def loopEnabled(self) -> bool:
        return self.__loop_enabled


class AsyncSetupBase(object):
    async def setup(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass


# TODO: This should really be a subclass of QtWidgets.QWidget, but somehow this screws up the
#   signals... Because of that, there are a bunch of 'type: ignore' overrides below.
class TimeViewMixin(ui_base.ProjectMixin):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)
    scaleXChanged = QtCore.pyqtSignal(fractions.Fraction)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # pixels per beat
        self.__scale_x = fractions.Fraction(500, 1)
        self.__x_offset = 0
        self.__content_width = 100
        self.project.duration_changed.add(lambda _: self.__updateContentWidth())

        self.setMinimumWidth(100)  # type: ignore

        self.__updateContentWidth()

    def __updateContentWidth(self) -> None:
        width = int(self.project.duration.fraction * self.__scale_x) + 120
        self.setContentWidth(width)

    def contentWidth(self) -> int:
        return self.__content_width

    def setContentWidth(self, width: int) -> None:
        if width == self.__content_width:
            return

        self.__content_width = width
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.setXOffset(min(self.xOffset(), self.maximumXOffset()))

    def maximumXOffset(self) -> int:
        return max(0, self.__content_width - self.width())  # type: ignore

    def pageWidth(self) -> int:
        return self.width()  # type: ignore

    def xOffset(self) -> int:
        return self.__x_offset

    def setXOffset(self, offset: int) -> None:
        offset = max(0, min(offset, self.maximumXOffset()))
        if offset == self.__x_offset:
            return

        dx = self.__x_offset - offset
        self.__x_offset = offset
        self.xOffsetChanged.emit(self.__x_offset)

        self.scroll(dx, 0)  # type: ignore

    def scaleX(self) -> fractions.Fraction:
        return self.__scale_x

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.__updateContentWidth()
        self.scaleXChanged.emit(self.__scale_x)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)  # type: ignore

        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.pageWidthChanged.emit(self.width())  # type: ignore


class TrackViewMixin(AsyncSetupBase, QtWidgets.QWidget):
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__current_track = None  # type: music.Track
        self.__tracks = {}  # type: Dict[int, base_track_item.BaseTrackItem]
        self.__group_listeners = {}  # type: Dict[int, core.Listener]
        self.__addTrack(self.project.master_group)

    async def setup(self) -> None:
        await super().setup()

    async def cleanup(self) -> None:
        for track_item in list(self.__tracks.values()):
            self.__removeSingleTrack(track_item.track)

        await super().cleanup()

    def tracks(self) -> Sequence[base_track_item.BaseTrackItem]:
        return [
            self.__tracks[track.id]
            for track in self.project.master_group.walk_tracks()]

    def track(self, track_id: int) -> base_track_item.BaseTrackItem:
        return self.__tracks[track_id]

    def currentTrack(self) -> music.Track:
        return self.__current_track

    def setCurrentTrack(self, track: music.Track) -> None:
        if track is self.__current_track:
            return

        if self.__current_track is not None:
            track_item = self.track(self.__current_track.id)
            track_item.setIsCurrent(False)
            self._current_track = None

        if track is not None:
            track_item = self.track(track.id)
            track_item.setIsCurrent(True)
            self.__current_track = track

        self.currentTrackChanged.emit(self.__current_track)

    def createTrack(self, track: music.Track) -> base_track_item.BaseTrackItem:
        raise NotImplementedError

    def updateTracks(self) -> None:
        pass

    def __addTrack(self, track: music.Track) -> None:
        for t in track.walk_tracks(groups=True, tracks=True):
            self.__addSingleTrack(t)
        self.updateTracks()

    def __addSingleTrack(self, track: music.Track) -> None:
        if isinstance(track, music.TrackGroup):
            track = cast(music.TrackGroup, track)
            listener = track.tracks_changed.add(functools.partial(self.__onTracksChanged, track))
            self.__group_listeners[track.id] = listener
        else:
            track_item = self.createTrack(track)
            self.__tracks[track.id] = track_item

    def __removeTrack(self, track: music.Track) -> None:
        for t in track.walk_tracks(groups=True, tracks=True):
            self.__removeSingleTrack(t)
        self.updateTracks()

    def __removeSingleTrack(self, track: music.Track) -> None:
        if isinstance(track, music.TrackGroup):
            listener = self.__group_listeners.pop(track.id)
            listener.remove()
        else:
            track_item = self.__tracks.pop(track.id)
            track_item.close()

    def __onTracksChanged(
            self, group: music.TrackGroup, change: model.PropertyListChange[music.Track]) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.__addTrack(change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.__removeTrack(change.old_value)

        else:  # pragma: no cover
            raise TypeError(type(change))


class Editor(
        TrackViewMixin, TimeViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)

    track_cls_map = {
        'ScoreTrack': score_track_item.ScoreTrackEditorItem,
        'BeatTrack': beat_track_item.BeatTrackEditorItem,
        'ControlTrack': control_track_item.ControlTrackEditorItem,
        'SampleTrack': sample_track_item.SampleTrackEditorItem,
    }  # type: Dict[str, Type[base_track_item.BaseTrackEditorItem]]

    def __init__(self, *, player_state: PlayerState, **kwargs: Any) -> None:
        self.__player_state = player_state

        self.__current_tool_box = None  # type: tools.ToolBox
        self.__current_tool = None  # type: tools.ToolBase
        self.__mouse_grabber = None  # type: base_track_item.BaseTrackEditorItem
        self.__current_track_item = None  # type: base_track_item.BaseTrackEditorItem
        self.__hover_track_item = None  # type: base_track_item.BaseTrackEditorItem

        self.__y_offset = 0
        self.__content_height = 100

        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(100)

        for idx, track_item in enumerate(self.tracks()):
            if idx == 0:
                self.__onCurrentTrackChanged(track_item.track)

        self.updateTracks()
        self.currentTrackChanged.connect(self.__onCurrentTrackChanged)

        self.__player_state.currentTimeChanged.connect(
            lambda time: self.setPlaybackPos(time, 1))

        self.scaleXChanged.connect(lambda _: self.updateTracks())

    def createTrack(self, track: music.Track) -> base_track_item.BaseTrackEditorItem:
        track_item_cls = self.track_cls_map[type(track).__name__]
        track_item = track_item_cls(
            track=track,
            player_state=self.__player_state,
            editor=self,
            context=self.context)
        track_item.rectChanged.connect(
            lambda rect: self.update(rect.translated(-self.offset())))
        track_item.sizeChanged.connect(
            lambda size: self.updateTracks())
        return track_item

    def updateTracks(self) -> None:
        self.__content_height = 0

        p = QtCore.QPoint(0, 0)
        for track_item in self.tracks():
            track_item.setScaleX(self.scaleX())
            track_item.setViewTopLeft(p)
            p += QtCore.QPoint(0, track_item.height())
            p += QtCore.QPoint(0, 3)

        self.__content_height = p.y() + 10

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))

        self.update()

    def __onCurrentTrackChanged(self, track: music.Track) -> None:
        if track is not None:
            track_item = down_cast(base_track_item.BaseTrackEditorItem, self.track(track.id))
            self.__current_track_item = track_item

            self.setCurrentToolBoxClass(track_item.toolBoxClass)

        else:
            self.__current_track_item = None
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
        for track_item in self.tracks():
            track_item.setPlaybackPos(current_time)

    def onClearSelection(self) -> None:
        if self.selection_set.empty():
            return

        self.send_command_async(music.Command(
            target=self.project.id,
            clear_measures=music.ClearMeasures(
                measure_ids=[
                    mref.id for mref in sorted(
                        (cast(base_track_item.MeasureEditorItem, measure_item).measure_reference
                         for measure_item in self.selection_set),
                        key=lambda mref: mref.index)])))

    def onPaste(self, *, mode: str) -> None:
        assert mode in ('overwrite', 'link')

        if self.selection_set.empty():
            return

        clipboard = self.app.clipboardContent()
        if clipboard['type'] == 'measures':
            self.send_command_async(music.Command(
                target=self.project.id,
                paste_measures=music.PasteMeasures(
                    mode=mode,
                    src_objs=[copy['data'] for copy in clipboard['data']],
                    target_ids=[
                        mref.id for mref in sorted(
                            (cast(base_track_item.MeasureEditorItem, measure_item).measure_reference
                             for measure_item in self.selection_set),
                            key=lambda mref: mref.index)])))

        else:
            raise ValueError(clipboard['type'])

    def trackItemAt(self, pos: QtCore.QPoint) -> base_track_item.BaseTrackEditorItem:
        p = -self.offset()
        for track_item in self.tracks():
            if p.y() <= pos.y() < p.y() + track_item.height():
                return down_cast(base_track_item.BaseTrackEditorItem, track_item)

            p += QtCore.QPoint(0, track_item.height())
            p += QtCore.QPoint(0, 3)

        return None

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.height())

    def setHoverTrackItem(
            self, track_item: Optional[base_track_item.BaseTrackEditorItem],
            evt: Union[None, QtGui.QEnterEvent, QtGui.QMouseEvent]
    ) -> None:
        if track_item is self.__hover_track_item:
            return

        if self.__hover_track_item is not None:
            track_evt = QtCore.QEvent(QtCore.QEvent.Leave)
            self.__hover_track_item.leaveEvent(track_evt)

        if track_item is not None:
            track_evt = QtGui.QEnterEvent(
                evt.localPos() + self.offset() - track_item.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos())
            track_item.enterEvent(track_evt)

        self.__hover_track_item = track_item

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        evt = down_cast(QtGui.QEnterEvent, evt)
        self.setHoverTrackItem(self.trackItemAt(evt.pos()), evt)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverTrackItem(None, None)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__mouse_grabber is not None:
            track_item = self.__mouse_grabber
        else:
            track_item = self.trackItemAt(evt.pos())
            self.setHoverTrackItem(track_item, evt)

        if track_item is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_item.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_item.mouseMoveEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        track_item = self.trackItemAt(evt.pos())
        if track_item is not None:
            if not track_item.isCurrent():
                self.setCurrentTrack(track_item.track)
                evt.accept()
                return

        if track_item is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_item.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_item.mousePressEvent(track_evt)
            if track_evt.isAccepted():
                self.__mouse_grabber = track_item
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
            self.__mouse_grabber.mouseReleaseEvent(track_evt)
            self.__mouse_grabber = None
            evt.setAccepted(track_evt.isAccepted())
            self.setHoverTrackItem(self.trackItemAt(evt.pos()), evt)
            return

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        track_item = self.trackItemAt(evt.pos())
        if track_item is not None:
            if not track_item.isCurrent():
                self.setCurrentTrack(track_item.track)
                evt.accept()
                return

        if track_item is not None:
            track_evt = QtGui.QMouseEvent(
                evt.type(),
                evt.localPos() + self.offset() - track_item.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_item.mouseDoubleClickEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        track_item = self.trackItemAt(evt.pos())
        if track_item is not None:
            track_evt = QtGui.QWheelEvent(
                evt.pos() + self.offset() - track_item.viewTopLeft(),
                evt.globalPos(),
                evt.pixelDelta(),
                evt.angleDelta(),
                0,
                Qt.Horizontal,
                evt.buttons(),
                evt.modifiers(),
                evt.phase(),
                evt.source())
            track_item.wheelEvent(track_evt)
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
            current_track_item = self.track(current_track.id)
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
            current_track_item.keyPressEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        current_track = self.currentTrack()
        if current_track is not None:
            current_track_item = self.track(current_track.id)
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
            current_track_item.keyReleaseEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        track_item = self.trackItemAt(evt.pos())
        if track_item is not None:
            menu = QtWidgets.QMenu()
            track_item.buildContextMenu(
                menu, evt.pos() + self.offset() - track_item.viewTopLeft())
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
            for track_item in self.tracks():
                track_rect = QtCore.QRect(
                    0, p.y(), max(self.contentWidth(), self.width()), track_item.height())
                track_rect = track_rect.intersected(evt.rect())
                if not track_rect.isEmpty():
                    painter.save()
                    try:
                        painter.setClipRect(track_rect)
                        painter.translate(p)
                        track_item.paint(painter, track_rect.translated(-p))
                    finally:
                        painter.restore()
                p += QtCore.QPoint(0, track_item.height())

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


class TimeLine(TimeViewMixin, ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(
            self, *, project_view: 'ProjectView', player_state: PlayerState, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)

        self.__project_view = project_view
        self.__player_state = player_state
        self.__player_id = None  # type: str
        self.__move_time = False
        self.__old_player_state = None  # type: bool

        self.__player_state.currentTimeChanged.connect(self.onCurrentTimeChanged)
        self.__player_state.loopStartTimeChanged.connect(lambda _: self.update())
        self.__player_state.loopEndTimeChanged.connect(lambda _: self.update())

        self.__duration_listener = self.project.duration_changed.add(self.onDurationChanged)

        self.scaleXChanged.connect(lambda _: self.update())

    def setPlayerID(self, player_id: str) -> None:
        self.__player_id = player_id

    def timeToX(self, time: audioproc.MusicalTime) -> int:
        x = 10
        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if time - measure.duration <= audioproc.MusicalTime(0, 1):
                return x + int(width * (time / measure.duration).fraction)

            x += width
            time -= measure.duration

        return x

    def xToTime(self, x: int) -> audioproc.MusicalTime:
        x -= 10
        time = audioproc.MusicalTime(0, 1)
        if x <= 0:
            return time

        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if x <= width:
                return time + measure.duration * fractions.Fraction(int(x), width)

            time += measure.duration
            x -= width

        return time

    def onSetLoopStart(self, loop_start_time: audioproc.MusicalTime) -> None:
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_start_time=loop_start_time.to_proto())))

    def onSetLoopEnd(self, loop_end_time: audioproc.MusicalTime) -> None:
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_end_time=loop_end_time.to_proto())))

    def onClearLoop(self) -> None:
        pass

    def onCurrentTimeChanged(self, current_time: audioproc.MusicalTime) -> None:
        if self.isVisible():
            x = self.timeToX(self.__player_state.currentTime())

            left = self.xOffset() + 1 * self.width() // 5
            right = self.xOffset() + 4 * self.width() // 5
            if x < left:
                self.setXOffset(max(0, x - 1 * self.width() // 5))
            elif x > right:
                self.setXOffset(x - 4 * self.width() // 5)

        self.update()

    def onDurationChanged(self, change: model.PropertyValueChange[float]) -> None:
        self.update()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if (self.__player_id is not None
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            self.__move_time = True
            self.__old_player_state = self.__player_state.playing()
            x = evt.pos().x() + self.xOffset()
            current_time = self.xToTime(x)
            self.call_async(
                self.project_client.update_player_state(
                    self.__player_id,
                    audioproc.PlayerState(playing=False)))
            self.__project_view.setPlaybackPosMode('manual')
            self.__player_state.setCurrentTime(current_time)
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__move_time:
            x = evt.pos().x() + self.xOffset()
            current_time = self.xToTime(x)
            self.__player_state.setCurrentTime(current_time)
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__move_time and evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            self.__move_time = False
            x = evt.pos().x() + self.xOffset()
            current_time = self.xToTime(x)
            self.call_async(
                self.project_client.update_player_state(
                    self.__player_id,
                    audioproc.PlayerState(
                        playing=self.__old_player_state,
                        current_time=current_time.to_proto())))
            self.__project_view.setPlaybackPosMode('follow')
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu()

        if not self.__player_state.playing() and self.__player_state.currentTime() is not None:
            set_loop_start = QtWidgets.QAction("Set loop start", menu)
            set_loop_start.triggered.connect(
                lambda _: self.onSetLoopStart(self.__player_state.currentTime()))
            menu.addAction(set_loop_start)

            set_loop_end = QtWidgets.QAction("Set loop end", menu)
            set_loop_end.triggered.connect(
                lambda _: self.onSetLoopEnd(self.__player_state.currentTime()))
            menu.addAction(set_loop_end)

        clear_loop = QtWidgets.QAction("Clear loop", menu)
        clear_loop.triggered.connect(lambda _: self.onClearLoop())
        menu.addAction(clear_loop)

        if not menu.isEmpty():
            menu.exec_(evt.globalPos())
            evt.accept()
            return

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        painter.fillRect(evt.rect(), Qt.white)

        painter.setPen(Qt.black)
        x = 10 - self.xOffset()
        measure_start_time = audioproc.MusicalTime()
        for midx, mref in enumerate(self.project.property_track.measure_list):
            measure = down_cast(music.PropertyMeasure, mref.measure)
            width = int(self.scaleX() * measure.duration.fraction)

            if x + width > evt.rect().x() and x < evt.rect().x() + evt.rect().width():
                if mref.is_first:
                    painter.fillRect(x, 0, 2, self.height(), Qt.black)
                else:
                    painter.fillRect(x, 0, 1, self.height(), Qt.black)

                if width > 100:
                    painter.drawText(x + 5, 12, '%d' % (midx + 1))

                for i in range(1, measure.time_signature.upper):
                    pos = int(width * i / measure.time_signature.lower)
                    painter.fillRect(x + pos, 0, 1, self.height() // 2, Qt.black)

                loop_start_time = self.__player_state.loopStartTime()
                if (loop_start_time is not None
                        and (measure_start_time <= loop_start_time
                             < measure_start_time + measure.duration)):
                    pos = int(
                        width
                        * ((loop_start_time - measure_start_time) / measure.duration).fraction)
                    painter.setBrush(Qt.black)
                    painter.setPen(Qt.NoPen)
                    polygon = QtGui.QPolygon()
                    polygon.append(QtCore.QPoint(x + pos, 0))
                    polygon.append(QtCore.QPoint(x + pos + 7, 0))
                    polygon.append(QtCore.QPoint(x + pos + 2, 5))
                    polygon.append(QtCore.QPoint(x + pos + 2, self.height() - 5))
                    polygon.append(QtCore.QPoint(x + pos + 7, self.height()))
                    polygon.append(QtCore.QPoint(x + pos, self.height()))
                    painter.drawPolygon(polygon)

                loop_end_time = self.__player_state.loopEndTime()
                if (loop_end_time is not None
                        and (measure_start_time <= loop_end_time
                             < measure_start_time + measure.duration)):
                    pos = int(
                        width * ((loop_end_time - measure_start_time) / measure.duration).fraction)
                    painter.setBrush(Qt.black)
                    painter.setPen(Qt.NoPen)
                    polygon = QtGui.QPolygon()
                    polygon.append(QtCore.QPoint(x + pos - 6, 0))
                    polygon.append(QtCore.QPoint(x + pos + 2, 0))
                    polygon.append(QtCore.QPoint(x + pos + 2, self.height()))
                    polygon.append(QtCore.QPoint(x + pos - 6, self.height()))
                    polygon.append(QtCore.QPoint(x + pos, self.height() - 6))
                    polygon.append(QtCore.QPoint(x + pos, 6))
                    painter.drawPolygon(polygon)

                playback_time = self.__player_state.currentTime()
                if measure_start_time <= playback_time < measure_start_time + measure.duration:
                    pos = int(
                        width * ((playback_time - measure_start_time) / measure.duration).fraction)
                    painter.fillRect(x + pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

            x += width
            measure_start_time += measure.duration

        painter.fillRect(x, 0, 2, self.height(), Qt.black)

        painter.end()


class TrackListItem(base_track_item.BaseTrackItem):
    def height(self) -> int:
        return {
            'ScoreTrack': 240,
            'BeatTrack': 60,
            'ControlTrack': 120,
            'SampleTrack': 120,
        }[type(self.track).__name__]

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        super().paint(painter, paint_rect)

        painter.setPen(Qt.black)
        painter.drawText(QtCore.QPoint(3, 20), self.track.name)


class TrackList(TrackViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setMinimumWidth(100)
        self.setMaximumWidth(200)

        self.__y_offset = 0
        self.__content_height = 400

    def createTrack(self, track: music.Track) -> TrackListItem:
        track_item = TrackListItem(track=track, context=self.context)
        track_item.rectChanged.connect(lambda _: self.update())
        return track_item

    def maximumYOffset(self) -> int:
        return max(0, self.__content_height - self.height())

    def pageHeight(self) -> int:
        return self.height()

    def yOffset(self) -> int:
        return self.__y_offset

    def setYOffset(self, offset: int) -> None:
        dy = self.__y_offset - offset
        if dy != 0:
            self.__y_offset = offset
            self.yOffsetChanged.emit(self.__y_offset)
            self.scroll(0, dy)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.width())

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        try:
            p = QtCore.QPoint(0, -self.__y_offset)
            for track_item in self.tracks():
                track_rect = QtCore.QRect(0, p.y(), self.width(), track_item.height())
                track_rect = track_rect.intersected(evt.rect())
                if not track_rect.isEmpty():
                    painter.save()
                    try:
                        painter.setClipRect(track_rect)
                        painter.translate(p)

                        track_item.paint(painter, track_rect.translated(-p))
                    finally:
                        painter.restore()
                p += QtCore.QPoint(0, track_item.height())

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


class ProjectView(ui_base.ProjectMixin, QtWidgets.QMainWindow):
    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    playingChanged = QtCore.pyqtSignal(bool)
    loopEnabledChanged = QtCore.pyqtSignal(bool)

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
        super().__init__(parent=None, flags=Qt.Widget, context=context, **kwargs)

        self.__session_prefix = 'projectview:%s:' % self.project.id
        self.__session_data_last_update = {}  # type: Dict[str, float]

        self.__player_id = None  # type: str
        self.__player_node_id = None  # type: str
        self.__player_status_listener = None  # type: core.Listener
        self.__playback_pos_mode = 'follow'

        self.__player_state = PlayerState(context=self.context)
        self.__player_state.playingChanged.connect(self.playingChanged)
        self.__player_state.loopEnabledChanged.connect(self.loopEnabledChanged)

        editor_tab = QtWidgets.QWidget()

        editor_frame = Frame(parent=editor_tab)
        self.__editor = Editor(
            player_state=self.__player_state,
            parent=editor_frame, context=self.context)
        editor_frame.setWidget(self.__editor)

        self.__editor.setScaleX(self.__get_session_value('scale_x', self.__editor.scaleX()))
        self.__editor.setXOffset(self.__get_session_value('x_offset', 0))
        self.__editor.setYOffset(self.__get_session_value('y_offset', 0))

        self.__editor.currentToolBoxChanged.connect(self.currentToolBoxChanged)
        self.__editor.scaleXChanged.connect(self.__updateScaleX)

        time_line_frame = Frame(parent=editor_tab)
        self.__time_line = TimeLine(
            project_view=self, player_state=self.__player_state,
            parent=time_line_frame, context=self.context)
        time_line_frame.setWidget(self.__time_line)

        track_list_frame = Frame(parent=editor_tab)
        track_list = TrackList(parent=track_list_frame, context=self.context)
        track_list_frame.setWidget(track_list)

        self.__time_line.setScaleX(self.__editor.scaleX())
        self.__time_line.setXOffset(self.__editor.xOffset())
        self.__editor.scaleXChanged.connect(self.__time_line.setScaleX)

        self.__editor.currentTrackChanged.connect(track_list.setCurrentTrack)
        track_list.currentTrackChanged.connect(self.__editor.setCurrentTrack)

        scroll_x = QtWidgets.QScrollBar(orientation=Qt.Horizontal, parent=editor_tab)
        scroll_x.setRange(0, self.__editor.maximumXOffset())
        scroll_x.setSingleStep(50)
        scroll_x.setPageStep(self.__editor.pageWidth())
        scroll_x.setValue(self.__editor.xOffset())
        scroll_y = QtWidgets.QScrollBar(orientation=Qt.Vertical, parent=editor_tab)
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
        scroll_y.valueChanged.connect(track_list.setYOffset)
        scroll_y.valueChanged.connect(self.__updateYOffset)

        layout = QtWidgets.QGridLayout()
        layout.setSpacing(1)
        layout.addWidget(track_list_frame, 1, 0, 1, 1)
        layout.addWidget(time_line_frame, 0, 1, 1, 1)
        layout.addWidget(editor_frame, 1, 1, 1, 1)
        layout.addWidget(scroll_x, 2, 0, 1, 2)
        layout.addWidget(scroll_y, 0, 2, 2, 1)
        editor_tab.setLayout(layout)

        mixer_tab = QtWidgets.QWidget()

        graph_tab = pipeline_graph_view.PipelineGraphView(context=self.context)

        project_tab = QtWidgets.QTabWidget(self)
        project_tab.setTabPosition(QtWidgets.QTabWidget.West)
        project_tab.setDocumentMode(True)
        project_tab.addTab(editor_tab, "Editor")
        project_tab.addTab(mixer_tab, "Mixer")
        project_tab.setTabEnabled(1, False)
        project_tab.addTab(graph_tab, "Graph")
        project_tab.setCurrentIndex(self.get_session_value(
            'project_view/current_tab_index', 0))
        project_tab.currentChanged.connect(functools.partial(
            self.set_session_value, 'project_view/current_tab_index'))
        self.setCentralWidget(project_tab)

        self._docks = []  # type: List[dock_widget.DockWidget]

        self._tools_dock = tool_dock.ToolsDockWidget(parent=self, context=self.context)
        self._docks.append(self._tools_dock)
        self.currentToolBoxChanged.connect(self._tools_dock.setCurrentToolBox)
        self._tools_dock.setCurrentToolBox(self.currentToolBox())

        self._project_properties_dock = project_properties_dock.ProjectPropertiesDockWidget(
            parent=self, context=self.context)
        self._docks.append(self._project_properties_dock)

        self._tracks_dock = tracks_dock.TracksDockWidget(parent=self, context=self.context)
        self._docks.append(self._tracks_dock)

        self._track_properties_dock = track_properties_dock.TrackPropertiesDockWidget(
            parent=self, context=self.context)
        self._docks.append(self._track_properties_dock)
        self._tracks_dock.currentTrackChanged.connect(self._track_properties_dock.setTrack)

    async def setup(self) -> None:
        self.__player_id, player_realm = await self.project_client.create_player(
            audioproc_address=self.audioproc_client.address)
        self.__player_status_listener = self.project_client.add_player_status_listener(
            self.__player_id, self.onPlayerStatus)

        self.__time_line.setPlayerID(self.__player_id)
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
            child_realm=player_realm,
            description=node_db.Builtins.ChildRealmDescription,)
        await self.audioproc_client.connect_ports(
            'root', self.__player_node_id, 'out:left', 'sink', 'in:left')
        await self.audioproc_client.connect_ports(
            'root', self.__player_node_id, 'out:right', 'sink', 'in:right')

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
            self.__time_line.setPlayerID(None)
            await self.project_client.delete_player(self.__player_id)
            self.__player_id = None

        self.__editor.close()

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
        self.__lazy_set_session_value('scale_x', scale)

    def __updateXOffset(self, offset: int) -> None:
        self.__lazy_set_session_value('x_offset', offset)

    def __updateYOffset(self, offset: int) -> None:
        self.__lazy_set_session_value('y_offset', offset)

    def playing(self) -> bool:
        return self.__player_state.playing()

    def loopEnabled(self) -> bool:
        return self.__player_state.loopEnabled()

    def setPlaybackPosMode(self, mode: str) -> None:
        assert mode in ('follow', 'manual')
        self.__playback_pos_mode = mode

    def currentToolBox(self) -> tools.ToolBox:
        return self.__editor.currentToolBox()

    async def createPluginUI(self, node_id: str) -> Tuple[int, Tuple[int, int]]:
        return await self.project_client.create_plugin_ui(self.__player_id, node_id)

    async def deletePluginUI(self, node_id: str) -> None:
        await self.project_client.delete_plugin_ui(self.__player_id, node_id)

    def onPlayerStatus(
            self, player_state: Optional[audioproc.PlayerState] = None,
            pipeline_state: Optional[str] = None, pipeline_disabled: Optional[bool] = None,
            **kwargs: Any) -> None:
        if player_state is not None and self.__playback_pos_mode == 'follow':
            self.__player_state.updateFromProto(player_state)

        if pipeline_state is not None:
            self.window.pipeline_status.setText(pipeline_state)
            logger.info("pipeline state: %s", pipeline_state)

        if pipeline_disabled:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setIcon(QtWidgets.QMessageBox.Critical)
            dialog.setWindowTitle("noisicaa - Crash")
            dialog.setText(
                "The audio pipeline has been disabled, because it is repeatedly crashing.")
            quit_button = dialog.addButton("Quit", QtWidgets.QMessageBox.DestructiveRole)
            undo_and_restart_button = dialog.addButton(
                "Undo last command and restart pipeline", QtWidgets.QMessageBox.ActionRole)
            restart_button = dialog.addButton("Restart pipeline", QtWidgets.QMessageBox.AcceptRole)
            dialog.setDefaultButton(restart_button)
            dialog.finished.connect(lambda _: self.call_async(
                self.onPipelineDisabledDialogFinished(
                    dialog, quit_button, undo_and_restart_button, restart_button)))
            dialog.show()

    async def onPipelineDisabledDialogFinished(
            self, dialog: QtWidgets.QMessageBox, quit_button: QtWidgets.QAbstractButton,
            undo_and_restart_button: QtWidgets.QAbstractButton,
            restart_button: QtWidgets.QAbstractButton) -> None:
        if dialog.clickedButton() == quit_button:
            self.app.quit()

        elif dialog.clickedButton() == restart_button:
            await self.project_client.restart_player_pipeline(self.__player_id)

        elif dialog.clickedButton() == undo_and_restart_button:
            await self.project_client.undo()
            await self.project_client.restart_player_pipeline(self.__player_id)

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
            measure_start_time = audioproc.MusicalTime()
            current_time = self.__player_state.currentTime()
            for mref in self.project.property_track.measure_list:
                measure = mref.measure
                if measure_start_time <= current_time < (measure_start_time + measure.duration
                                                         + audioproc.MusicalDuration(1, 16)):
                    new_time = measure_start_time
                    break

                measure_start_time += measure.duration

        elif where == 'next':
            measure_start_time = audioproc.MusicalTime()
            current_time = self.__player_state.currentTime()
            for mref in self.project.property_track.measure_list:
                measure = mref.measure
                if measure_start_time <= current_time < measure_start_time + measure.duration:
                    new_time = measure_start_time + measure.duration
                    break

                measure_start_time += measure.duration

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
        items = [down_cast(base_track_item.MeasureEditorItem, item) for item in self.selection_set]
        for item in sorted(items, key=lambda item: item.measure_reference.index):
            data.append(item.getCopy())

        self.app.setClipboardContent({'type': 'measures', 'data': data})

    def onPaste(self, *, mode: str) -> None:
        self.__editor.onPaste(mode=mode)

    def onRender(self) -> None:
        dialog = render_dialog.RenderDialog(parent=self, context=self.context)
        dialog.setModal(True)
        dialog.show()

    def onSetNumMeasures(self) -> None:
        dialog = QtWidgets.QInputDialog(self)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)
        dialog.setIntRange(1, 1000)
        dialog.setIntValue(len(self.project.property_track.measure_list))
        dialog.setLabelText("Number of measures:")
        dialog.setWindowTitle("noisicaa - Set # measures")
        dialog.accepted.connect(lambda: self.send_command_async(music.Command(
            target=self.project.id,
            set_num_measures=music.SetNumMeasures(num_measures=dialog.intValue()))))
        dialog.show()
