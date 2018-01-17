#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import time
import uuid

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import music
from noisicaa import node_db
from noisicaa.music import model
from . import tool_dock
from . import project_properties_dock
from . import tracks_dock
from . import track_properties_dock
from . import pipeline_graph_view
from . import tool_dock
from . import ui_base
from . import tools
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__session_prefix = 'player_state:%s:' % self.project.id
        self.__last_current_time_update = None

        self.__playing = False
        self.__current_time = self.__get_session_value('current_time', audioproc.MusicalTime())
        self.__loop_start_time = self.__get_session_value('loop_start_time', None)
        self.__loop_end_time = self.__get_session_value('loop_end_time', None)
        self.__loop_enabled = self.__get_session_value('loop_enabled', False)

        self.__player_id = None

    def __get_session_value(self, key, default):
        return self.get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key, value):
        self.set_session_value(self.__session_prefix + key, value)

    def playerID(self):
        return self.__player_id

    def setPlayerID(self, player_id):
        self.__player_id = player_id

    def updateFromProto(self, player_state):
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

    def setPlaying(self, playing):
        if playing == self.__playing:
            return

        self.__playing = playing
        self.playingChanged.emit(playing)

    def playing(self):
        return self.__playing

    def setCurrentTime(self, current_time):
        if current_time == self.__current_time:
            return

        self.__current_time = current_time
        if (self.__last_current_time_update is None
            or time.time() - self.__last_current_time_update > 5):
            self.__set_session_value('current_time', current_time)
            self.__last_current_time_update = time.time()
        self.currentTimeChanged.emit(current_time)

    def currentTime(self):
        return self.__current_time

    def currentTimeProto(self):
        return self.__current_time.to_proto()

    def setLoopStartTime(self, loop_start_time):
        if loop_start_time == self.__loop_start_time:
            return

        self.__loop_start_time = loop_start_time
        self.__set_session_value('loop_start_time', loop_start_time)
        self.loopStartTimeChanged.emit(loop_start_time)

    def loopStartTime(self):
        return self.__loop_start_time

    def loopStartTimeProto(self):
        if self.__loop_start_time is not None:
            return self.__loop_start_time.to_proto()
        else:
            return None

    def setLoopEndTime(self, loop_end_time):
        if loop_end_time == self.__loop_end_time:
            return

        self.__loop_end_time = loop_end_time
        self.__set_session_value('loop_end_time', loop_end_time)
        self.loopEndTimeChanged.emit(loop_end_time)

    def loopEndTime(self):
        return self.__loop_end_time

    def loopEndTimeProto(self):
        if self.__loop_end_time is not None:
            return self.__loop_end_time.to_proto()
        else:
            return None

    def setLoopEnabled(self, loop_enabled):
        loop_enabled = bool(loop_enabled)
        if loop_enabled == self.__loop_enabled:
            return

        self.__loop_enabled = loop_enabled
        self.__set_session_value('loop_enabled', loop_enabled)
        self.loopEnabledChanged.emit(loop_enabled)

    def loopEnabled(self):
        return self.__loop_enabled


class AsyncSetupBase(object):
    async def setup(self):
        pass

    async def cleanup(self):
        pass


class TimeViewMixin(object):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)
    scaleXChanged = QtCore.pyqtSignal(fractions.Fraction)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # pixels per beat
        self.__scale_x = fractions.Fraction(500, 1)
        self.__x_offset = 0
        self.__content_width = 100
        self.project.listeners.add('duration', lambda *_: self.__updateContentWidth())

        self.setMinimumWidth(100)

        self.__updateContentWidth()

    def __updateContentWidth(self):
        width = int(self.project.duration.fraction * self.__scale_x) + 120
        self.setContentWidth(width)

    def contentWidth(self):
        return self.__content_width

    def setContentWidth(self, width):
        if width == self.__content_width:
            return

        self.__content_width = width
        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.setXOffset(min(self.xOffset(), self.maximumXOffset()))

    def maximumXOffset(self):
        return max(0, self.__content_width - self.width())

    def pageWidth(self):
        return self.width()

    def xOffset(self):
        return self.__x_offset

    def setXOffset(self, offset):
        offset = max(0, min(offset, self.maximumXOffset()))
        if offset == self.__x_offset:
            return

        dx = self.__x_offset - offset
        self.__x_offset = offset
        self.xOffsetChanged.emit(self.__x_offset)

        self.scroll(dx, 0)

    def scaleX(self):
        return self.__scale_x

    def setScaleX(self, scale_x):
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.__updateContentWidth()
        self.scaleXChanged.emit(self.__scale_x)

    def resizeEvent(self, evt):
        super().resizeEvent(evt)

        self.maximumXOffsetChanged.emit(self.maximumXOffset())
        self.pageWidthChanged.emit(self.width())


class TrackViewMixin(object):
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__current_track = None
        self.__tracks = {}
        self.__group_listeners = {}
        self.__addTrack(self.project.master_group)

    async def setup(self):
        await super().setup()

    async def cleanup(self):
        while len(self.__tracks) > 0:
            self.__removeTrack(next(self.__tracks.values()))

        await super().cleanup()

    def tracks(self):
        return [
            self.__tracks[track.id]
            for track in self.project.master_group.walk_tracks()]

    def track(self, track_id):
        return self.__tracks[track_id]

    def currentTrack(self):
        return self.__current_track

    def setCurrentTrack(self, track):
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

    def createTrack(self, track):
        raise NotImplementedError

    def updateTracks(self):
        pass

    def __addTrack(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            self.__addSingleTrack(t)
        self.updateTracks()

    def __addSingleTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = track.listeners.add(
                'tracks',
                functools.partial(self.__onTracksChanged, track))
            self.__group_listeners[track.id] = listener
        else:
            track_item = self.createTrack(track)
            self.__tracks[track.id] = track_item

    def __removeTrack(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            self.__removeSingleTrack(t)
        self.updateTracks()

    def __removeSingleTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = self.__group_listeners.pop(track.id)
            listener.remove()
        else:
            track_item = self.__tracks.pop(track.id)
            track_item.close()

    def __onTracksChanged(self, group, action, *args):
        if action == 'insert':
            idx, track = args
            self.__addTrack(track)

        elif action == 'delete':
            idx, track = args
            self.__removeTrack(track)

        else:  # pragma: no cover
            raise ValueError("Unknown action %r" % action)


class Editor(TrackViewMixin, TimeViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)

    track_cls_map = {
        'ScoreTrack': score_track_item.ScoreTrackEditorItem,
        'BeatTrack': beat_track_item.BeatTrackEditorItem,
        'ControlTrack': control_track_item.ControlTrackEditorItem,
        'SampleTrack': sample_track_item.SampleTrackEditorItem,
    }

    def __init__(self, *, player_state, **kwargs):
        self.__player_state = player_state

        self.__current_tool_box = None
        self.__current_tool = None
        self.__mouse_grabber = None
        self.__current_track_item = None
        self.__hover_track_item = None

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

    def createTrack(self, track):
        track_item_cls = self.track_cls_map[type(track).__name__]
        track_item = track_item_cls(
            track=track,
            player_state=self.__player_state,
            editor=self,
            **self.context_args)
        track_item.rectChanged.connect(
            lambda rect: self.update(rect.translated(-self.offset())))
        track_item.sizeChanged.connect(
            lambda size: self.updateTracks())
        return track_item

    def updateTracks(self):
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

    def __onCurrentTrackChanged(self, track):
        if track is not None:
            track_item = self.track(track.id)
            self.__current_track_item = track_item

            self.setCurrentToolBoxClass(track_item.toolBoxClass)

        else:
            self.__current_track_item = None
            self.setCurrentToolBoxClass(None)

    def currentToolBox(self):
        return self.__current_tool_box

    def setCurrentToolBoxClass(self, cls):
        if type(self.__current_tool_box) is cls:
            return
        logger.debug("Switching to tool box class %s", cls)

        if self.__current_tool_box is not None:
            self.__current_tool_box.currentToolChanged.disconnect(self.__onCurrentToolChanged)
            self.__onCurrentToolChanged(None)
            self.__current_tool_box = None

        if cls is not None:
            self.__current_tool_box = cls(**self.context_args)
            self.__onCurrentToolChanged(self.__current_tool_box.currentTool())
            self.__current_tool_box.currentToolChanged.connect(self.__onCurrentToolChanged)

        self.currentToolBoxChanged.emit(self.__current_tool_box)

    def __onCurrentToolChanged(self, tool):
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

    def __onToolCursorChanged(self, cursor):
        logger.debug("Cursor changed: %s", cursor)
        if cursor is not None:
            self.setCursor(cursor)
        else:
            self.setCursor(QtGui.QCursor(Qt.ArrowCursor))

    def maximumYOffset(self):
        return max(0, self.__content_height - self.height())

    def pageHeight(self):
        return self.height()

    def yOffset(self):
        return self.__y_offset

    def setYOffset(self, offset):
        if offset == self.__y_offset:
            return

        dy = self.__y_offset - offset
        self.__y_offset = offset
        self.yOffsetChanged.emit(self.__y_offset)

        self.scroll(0, dy)

    def offset(self):
        return QtCore.QPoint(self.xOffset(), self.__y_offset)

    def setPlaybackPos(self, current_time, num_samples):
        for track_item in self.tracks():
            track_item.setPlaybackPos(current_time)

    def onClearSelection(self):
        if self.selection_set.empty():
            return

        self.send_command_async(
            self.project.id, 'ClearMeasures',
            measure_ids=[
                mref.id for mref in sorted(
                    (measure_item.measure_reference
                     for measure_item in self.selection_set),
                    key=lambda mref: mref.index)])

    def onPaste(self, *, mode):
        assert mode in ('overwrite', 'link')

        if self.selection_set.empty():
            return

        clipboard = self.app.clipboardContent()
        if clipboard['type'] == 'measures':
            self.send_command_async(
                self.project.id, 'PasteMeasures',
                mode=mode,
                src_objs=[copy['data'] for copy in clipboard['data']],
                target_ids=[
                    mref.id for mref in sorted(
                        (measure_item.measure_reference
                         for measure_item in self.selection_set),
                        key=lambda mref: mref.index)])

        else:
            raise ValueError(clipboard['type'])

    def trackItemAt(self, pos):
        p = -self.offset()
        for track_item in self.tracks():
            if p.y() <= pos.y() < p.y() + track_item.height():
                return track_item

            p += QtCore.QPoint(0, track_item.height())
            p += QtCore.QPoint(0, 3)

        return None

    def resizeEvent(self, evt):
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.height())

    def setHoverTrackItem(self, track_item, evt):
        if track_item is self.__hover_track_item:
            return

        if self.__hover_track_item is not None:
            track_evt = QtCore.QEvent(
                QtCore.QEvent.Leave)
            self.__hover_track_item.leaveEvent(track_evt)

        if track_item is not None:
            track_evt = QtGui.QEnterEvent(
                evt.localPos() + self.offset() - track_item.viewTopLeft(),
                evt.windowPos(),
                evt.screenPos())
            track_item.enterEvent(track_evt)

        self.__hover_track_item = track_item

    def enterEvent(self, evt):
        self.setHoverTrackItem(self.trackItemAt(evt.pos()), evt)

    def leaveEvent(self, evt):
        self.setHoverTrackItem(None, evt)

    def mouseMoveEvent(self, evt):
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

    def mousePressEvent(self, evt):
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

    def mouseReleaseEvent(self, evt):
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

    def mouseDoubleClickEvent(self, evt):
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

    def wheelEvent(self, evt):
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

    def keyPressEvent(self, evt):
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

    def keyReleaseEvent(self, evt):
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

    def contextMenuEvent(self, evt):
        track_item = self.trackItemAt(evt.pos())
        if track_item is not None:
            menu = QtWidgets.QMenu()
            track_item.buildContextMenu(
                menu,
                evt.pos() + self.offset() - track_item.viewTopLeft())
            if not menu.isEmpty():
                menu.exec_(evt.globalPos())
                evt.accept()
                return

    def paintEvent(self, evt):
        super().paintEvent(evt)

        t1 = time.perf_counter()

        painter = QtGui.QPainter(self)

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

        painter.end()

        t2 = time.perf_counter()

        #logger.info("Editor.paintEvent(%s): %.2fµs", evt.rect(), 1e6 * (t2 - t1))


class TimeLine(TimeViewMixin, ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, *, project_view, player_state, **kwargs):
        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)

        self.__project_view = project_view
        self.__player_state = player_state
        self.__player_id = None
        self.__move_time = False
        self.__old_player_state = None

        self.__player_state.currentTimeChanged.connect(self.onCurrentTimeChanged)
        self.__player_state.loopStartTimeChanged.connect(lambda _: self.update())
        self.__player_state.loopEndTimeChanged.connect(lambda _: self.update())

        self.__duration_listener = self.project.listeners.add('duration', self.onDurationChanged)

        self.scaleXChanged.connect(lambda _: self.update())

    def setPlayerID(self, player_id):
        self.__player_id = player_id

    def timeToX(self, time):
        x = 10
        for mref in self.project.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration.fraction)

            if time - measure.duration <= audioproc.MusicalTime(0, 1):
                return x + int(width * (time / measure.duration).fraction)

            x += width
            time -= measure.duration

        return x

    def xToTime(self, x):
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

    def onSetLoopStart(self, loop_start_time):
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_start_time=loop_start_time.to_proto())))

    def onSetLoopEnd(self, loop_end_time):
        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_end_time=loop_end_time.to_proto())))

    def onClearLoop(self):
        pass

    def onCurrentTimeChanged(self, current_time):
        if self.isVisible():
            x = self.timeToX(self.__player_state.currentTime())

            left = self.xOffset() + 1 * self.width() / 5
            right = self.xOffset() + 4 * self.width() / 5
            if x < left:
                self.setXOffset(max(0, x - 1 * self.width() / 5))
            elif x > right:
                self.setXOffset(x - 4 * self.width() / 5)

        self.update()

    def onDurationChanged(self, old_value, new_value):
        self.update()

    def mousePressEvent(self, evt):
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

    def mouseMoveEvent(self, evt):
        if self.__move_time:
            x = evt.pos().x() + self.xOffset()
            current_time = self.xToTime(x)
            self.__player_state.setCurrentTime(current_time)
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if (self.__move_time
            and evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.NoModifier):
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

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()

        if (not self.__player_state.playing()
            and self.__player_state.currentTime() is not None):
            menu.addAction(QtWidgets.QAction(
                "Set loop start", menu,
                triggered=lambda _: self.onSetLoopStart(self.__player_state.currentTime())))
            menu.addAction(QtWidgets.QAction(
                "Set loop end", menu,
                triggered=lambda _: self.onSetLoopEnd(self.__player_state.currentTime())))

        menu.addAction(QtWidgets.QAction(
            "Clear loop", menu,
            triggered=lambda _: self.onClearLoop()))

        if not menu.isEmpty():
            menu.exec_(evt.globalPos())
            evt.accept()
            return

    def paintEvent(self, evt):
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        painter.fillRect(evt.rect(), Qt.white)

        painter.setPen(Qt.black)
        x = 10 - self.xOffset()
        measure_start_time = audioproc.MusicalTime()
        for midx, mref in enumerate(self.project.property_track.measure_list):
            measure = mref.measure
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
                        and measure_start_time <= loop_start_time < measure_start_time + measure.duration):
                    pos = int(width * ((loop_start_time - measure_start_time) / measure.duration).fraction)
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
                        and measure_start_time <= loop_end_time < measure_start_time + measure.duration):
                    pos = int(width * ((loop_end_time - measure_start_time) / measure.duration).fraction)
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
                    pos = int(width * ((playback_time - measure_start_time) / measure.duration).fraction)
                    painter.fillRect(x + pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

            x += width
            measure_start_time += measure.duration

        painter.fillRect(x, 0, 2, self.height(), Qt.black)

        painter.end()


class TrackListItem(base_track_item.BaseTrackItem):
    def height(self):
        return {
            'ScoreTrack': 240,
            'BeatTrack': 60,
            'ControlTrack': 120,
            'SampleTrack': 120,
        }[type(self.track).__name__]

    def paint(self, painter, paintRect):
        super().paint(painter, paintRect)

        painter.setPen(Qt.black)
        painter.drawText(QtCore.QPoint(3, 20), self.track.name)


class TrackList(TrackViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setMinimumWidth(100)
        self.setMaximumWidth(200)

        self.__y_offset = 0
        self.__content_height = 400

    def createTrack(self, track):
        track_item = TrackListItem(track=track, **self.context_args)
        track_item.rectChanged.connect(lambda _: self.update())
        return track_item

    def maximumYOffset(self):
        return max(0, self.__content_height - self.height())

    def pageHeight(self):
        return self.height()

    def yOffset(self):
        return self.__y_offset

    def setYOffset(self, offset):
        dy = self.__y_offset - offset
        if dy != 0:
            self.__y_offset = offset
            self.yOffsetChanged.emit(self.__y_offset)
            self.scroll(0, dy)

    def resizeEvent(self, evt):
        super().resizeEvent(evt)

        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))
        self.pageHeightChanged.emit(self.width())

    def paintEvent(self, evt):
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)

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

        painter.end()


class Frame(QtWidgets.QFrame):
    def __init__(self, parent):
        super().__init__(parent)

        self.setFrameStyle(QtWidgets.QFrame.Sunken | QtWidgets.QFrame.Panel)
        self.__layout = QtWidgets.QVBoxLayout()
        self.__layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.__layout.setContentsMargins(1, 1, 1, 1)
        self.setLayout(self.__layout)

    def setWidget(self, widget):
        self.__layout.addWidget(widget, 1)


class ProjectView(ui_base.ProjectMixin, QtWidgets.QMainWindow):
    currentToolBoxChanged = QtCore.pyqtSignal(tools.ToolBox)
    playingChanged = QtCore.pyqtSignal(bool)
    loopEnabledChanged = QtCore.pyqtSignal(bool)

    def __init__(self, **kwargs):
        super().__init__(parent=None, flags=Qt.Widget, **kwargs)

        self.__session_prefix = 'projectview:%s:' % self.project.id
        self.__session_data_last_update = {}

        self.__player_id = None
        self.__player_stream_address = None
        self.__player_node_id = None
        self.__player_status_listener = None
        self.__playback_pos_mode = 'follow'

        self.player_audioproc_address = None

        self.__player_state = PlayerState(**self.context_args)
        self.__player_state.playingChanged.connect(self.playingChanged)
        self.__player_state.loopEnabledChanged.connect(self.loopEnabledChanged)

        editor_tab = QtWidgets.QWidget()

        editor_frame = Frame(parent=editor_tab)
        self.__editor = Editor(
            player_state=self.__player_state,
            parent=editor_frame, **self.context_args)
        editor_frame.setWidget(self.__editor)

        self.__editor.setScaleX(self.__get_session_value('scale_x', self.__editor.scaleX()))
        self.__editor.setXOffset(self.__get_session_value('x_offset', 0))
        self.__editor.setYOffset(self.__get_session_value('y_offset', 0))

        self.__editor.currentToolBoxChanged.connect(self.currentToolBoxChanged)
        self.__editor.scaleXChanged.connect(self.__updateScaleX)

        time_line_frame = Frame(parent=editor_tab)
        self.__time_line = TimeLine(
            project_view=self, player_state=self.__player_state,
            parent=time_line_frame, **self.context_args)
        time_line_frame.setWidget(self.__time_line)

        track_list_frame = Frame(parent=editor_tab)
        track_list = TrackList(parent=track_list_frame, **self.context_args)
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

        graph_tab = pipeline_graph_view.PipelineGraphView(**self.context_args)

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

        self._docks = []

        self._tools_dock = tool_dock.ToolsDockWidget(parent=self, **self.context_args)
        self._docks.append(self._tools_dock)
        self.currentToolBoxChanged.connect(self._tools_dock.setCurrentToolBox)
        self._tools_dock.setCurrentToolBox(self.currentToolBox())

        self._project_properties_dock = project_properties_dock.ProjectPropertiesDockWidget(
            parent=self, **self.context_args)
        self._docks.append(self._project_properties_dock)

        self._tracks_dock = tracks_dock.TracksDockWidget(parent=self, **self.context_args)
        self._docks.append(self._tracks_dock)

        self._track_properties_dock = track_properties_dock.TrackPropertiesDockWidget(
            parent=self, **self.context_args)
        self._docks.append(self._track_properties_dock)
        self._tracks_dock.currentTrackChanged.connect(self._track_properties_dock.setTrack)

    async def setup(self):
        self.__player_id, self.__player_stream_address = await self.project_client.create_player()
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

        self.player_audioproc_address = await self.project_client.get_player_audioproc_address(
            self.__player_id)

        self.__player_node_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            description=node_db.IPCDescription,
            id=self.__player_node_id,
            initial_parameters=dict(ipc_address=self.__player_stream_address))
        await self.audioproc_client.connect_ports(
            self.__player_node_id, 'out:left', 'sink', 'in:left')
        await self.audioproc_client.connect_ports(
            self.__player_node_id, 'out:right', 'sink', 'in:right')

    async def cleanup(self):
        if self.__player_node_id is not None:
            await self.audioproc_client.disconnect_ports(
                self.__player_node_id, 'out:left', 'sink', 'in:left')
            await self.audioproc_client.disconnect_ports(
                self.__player_node_id, 'out:right', 'sink', 'in:right')
            await self.audioproc_client.remove_node(
                self.__player_node_id)
            self.__player_node_id = None
            self.__player_stream_address = None

        if self.__player_status_listener is not None:
            self.__player_status_listener.remove()
            self.__player_status_listener = None

        if self.__player_id is not None:
            self.__time_line.setPlayerID(None)
            await self.project_client.delete_player(self.__player_id)
            self.__player_id = None

        self.__editor.close()

    def __get_session_value(self, key, default):
        return self.get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key, value):
        self.set_session_value(self.__session_prefix + key, value)

    def __lazy_set_session_value(self, key, value):
        # TODO: value should be stored to session 5sec after most recent change. I.e. need
        #   some timer...
        last_time = self.__session_data_last_update.get(key, 0)
        if time.time() - last_time > 5:
            self.__set_session_value(key, value)
            self.__session_data_last_update[key] = time.time()

    def __updateScaleX(self, scale):
        self.__lazy_set_session_value('scale_x', scale)

    def __updateXOffset(self, offset):
        self.__lazy_set_session_value('x_offset', offset)

    def __updateYOffset(self, offset):
        self.__lazy_set_session_value('y_offset', offset)

    def playing(self):
        return self.__player_state.playing()

    def loopEnabled(self):
        return self.__player_state.loopEnabled()

    def setPlaybackPosMode(self, mode):
        assert mode in ('follow', 'manual')
        self.__playback_pos_mode = mode

    def currentToolBox(self):
        return self.__editor.currentToolBox()

    def onPlayerStatus(
            self, player_state=None, pipeline_state=None, pipeline_disabled=None, **kwargs):
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
            self, dialog, quit_button, undo_and_restart_button, restart_button):
        if dialog.clickedButton() == quit_button:
            self.app.quit()

        elif dialog.clickedButton() == restart_button:
            await self.project_client.restart_player_pipeline(self.__player_id)

        elif dialog.clickedButton() == undo_and_restart_button:
            await self.project_client.undo()
            await self.project_client.restart_player_pipeline(self.__player_id)

    def onPlayerMoveTo(self, where):
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

    def onPlayerToggle(self):
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(playing=not self.__player_state.playing())))

    def onPlayerLoop(self, loop):
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.update_player_state(
                self.__player_id,
                audioproc.PlayerState(loop_enabled=loop)))

    def onClearSelection(self):
        self.__editor.onClearSelection()

    def onCopy(self):
        if self.selection_set.empty():
            return

        self.call_async(self.onCopyAsync())

    async def onCopyAsync(self):
        data = []
        for item in sorted(self.selection_set, key=lambda item: item.measure_reference.index):
            data.append(await item.getCopy())

        self.app.setClipboardContent(
            {'type': 'measures', 'data': data})

    def onPaste(self, *, mode):
        self.__editor.onPaste(mode=mode)

    def onSetNumMeasures(self):
        dialog = QtWidgets.QInputDialog(self)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)
        dialog.setIntRange(1, 1000)
        dialog.setIntValue(len(self.project.property_track.measure_list))
        dialog.setLabelText("Number of measures:")
        dialog.setWindowTitle("noisicaa - Set # measures")
        dialog.accepted.connect(lambda: self.send_command_async(
            self.project.id, 'SetNumMeasures',
            num_measures=dialog.intValue()))
        dialog.show()
