#!/usr/bin/python3

from fractions import Fraction
import functools
import logging
import time

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.music import model
from noisicaa.music import time_mapper
from noisicaa.ui import tools
from noisicaa.ui import ui_base
from noisicaa.ui import selection_set
from . import base_track_item
from . import score_track_item
from . import beat_track_item
from . import control_track_item
from . import sample_track_item

logger = logging.getLogger(__name__)


class AsyncSetupBase(object):
    async def setup(self):
        pass

    async def cleanup(self):
        pass


class PlayerState(ui_base.ProjectMixin, QtCore.QObject):
    stateChanged = QtCore.pyqtSignal(str)
    playbackSamplePosChanged = QtCore.pyqtSignal(object)
    loopStartSamplePosChanged = QtCore.pyqtSignal(object)
    loopEndSamplePosChanged = QtCore.pyqtSignal(object)
    loopChanged = QtCore.pyqtSignal(bool)

    def __init__(self, sheet, time_mapper, **kwargs):
        super().__init__(**kwargs)

        self.__time_mapper = time_mapper
        self.__session_prefix = 'player_state:%s' % sheet.id
        self.__last_playback_sample_pos_update = None

        self.__state = 'stopped'
        self.__playback_sample_pos = self.__get_session_value('playback_sample_pos', 0)
        self.__loop_start_sample_pos = self.__get_session_value('loop_start_sample_pos', None)
        self.__loop_end_sample_pos = self.__get_session_value('loop_end_sample_pos', None)
        self.__loop = self.__get_session_value('loop', False)

        self.__player_id = None

    def __get_session_value(self, key, default):
        return super().get_session_value(self.__session_prefix + key, default)

    def __set_session_value(self, key, value):
        super().set_session_value(self.__session_prefix + key, value)

    def playerID(self):
        return self.__player_id

    def setPlayerID(self, player_id):
        self.__player_id = player_id

    def setState(self, state):
        if state == self.__state:
            return

        self.__state = state
        self.stateChanged.emit(state)

    def state(self):
        return self.__state

    def setPlaybackSamplePos(self, sample_pos):
        if sample_pos == self.__playback_sample_pos:
            return

        self.__playback_sample_pos = sample_pos
        if (self.__last_playback_sample_pos_update is None
            or time.time() - self.__last_playback_sample_pos_update > 5):
            self.__set_session_value('playback_sample_pos', sample_pos)
            self.__last_playback_sample_pos_update = time.time()
        self.playbackSamplePosChanged.emit(sample_pos)

    def playbackSamplePos(self):
        return self.__playback_sample_pos

    def playbackTimepos(self):
        return self.__time_mapper.sample2timepos(self.__playback_sample_pos)

    def setLoopStartSamplePos(self, sample_pos):
        if sample_pos == self.__loop_start_sample_pos:
            return

        self.__loop_start_sample_pos = sample_pos
        self.__set_session_value('loop_start_sample_pos', sample_pos)
        self.loopStartSamplePosChanged.emit(sample_pos)

    def loopStartSamplePos(self):
        return self.__loop_start_sample_pos

    def loopStartTimepos(self):
        if self.__loop_start_sample_pos is None:
            return None
        return self.__time_mapper.sample2timepos(self.__loop_start_sample_pos)

    def setLoopEndSamplePos(self, sample_pos):
        if sample_pos == self.__loop_end_sample_pos:
            return

        self.__loop_end_sample_pos = sample_pos
        self.__set_session_value('loop_end_sample_pos', sample_pos)
        self.loopEndSamplePosChanged.emit(sample_pos)

    def loopEndSamplePos(self):
        return self.__loop_end_sample_pos

    def loopEndTimepos(self):
        if self.__loop_end_sample_pos is None:
            return None
        return self.__time_mapper.sample2timepos(self.__loop_end_sample_pos)

    def setLoop(self, loop):
        loop = bool(loop)
        if loop == self.__loop:
            return

        self.__loop = loop
        self.__set_session_value('loop', loop)
        self.loopChanged.emit(loop)

    def loop(self):
        return self.__loop


class TrackViewMixin(object):
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, sheet, **kwargs):
        super().__init__(**kwargs)

        self.__sheet = sheet
        self.__current_track = None
        self.__tracks = {}
        self.__group_listeners = {}
        self.__addTrack(self.__sheet.master_group)

    async def setup(self):
        await super().setup()

    async def cleanup(self):
        while len(self.__tracks) > 0:
            self.__removeTrack(next(self.__tracks.values()))

        await super().cleanup()

    def tracks(self):
        return [
            self.__tracks[track.id]
            for track in self.__sheet.master_group.walk_tracks()]

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


class SheetEditor(TrackViewMixin, ui_base.ProjectMixin, AsyncSetupBase, QtWidgets.QWidget):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    maximumYOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    yOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)
    pageHeightChanged = QtCore.pyqtSignal(int)

    scaleXChanged = QtCore.pyqtSignal(Fraction)

    currentToolChanged = QtCore.pyqtSignal(tools.Tool)
    supportedToolsChanged = QtCore.pyqtSignal(set)

    track_cls_map = {
        'ScoreTrack': score_track_item.ScoreTrackEditorItem,
        'BeatTrack': beat_track_item.BeatTrackEditorItem,
        'ControlTrack': control_track_item.ControlTrackEditorItem,
        'SampleTrack': sample_track_item.SampleTrackEditorItem,
    }

    def __init__(self, *, sheet, player_state, **kwargs):
        self.__sheet = sheet
        self.__player_state = player_state

        self.__current_tool = None
        self.__mouse_grabber = None
        self.__current_track_item = None
        self.__hover_track_item = None

        # pixels per beat
        self.__scale_x = Fraction(500, 1)

        self.__x_offset = 0
        self.__y_offset = 0
        self.__content_width = 100
        self.__content_height = 100

        self.__time_mapper = music.TimeMapper(self.__sheet)

        self.__selection_set = selection_set.SelectionSet()

        super().__init__(sheet, **kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(100)
        self.setMinimumHeight(100)

        for idx, track_item in enumerate(self.tracks()):
            if idx == 0:
                self.__onCurrentTrackChanged(track_item.track)

        self.updateTracks()
        self.currentTrackChanged.connect(
            self.__onCurrentTrackChanged)

        self.__player_state.playbackSamplePosChanged.connect(
            lambda sample_pos: self.setPlaybackPos(sample_pos, 1))

    def createTrack(self, track):
        track_item_cls = self.track_cls_map[type(track).__name__]
        track_item = track_item_cls(
            **self.context, track=track, player_state=self.__player_state)
        track_item.rectChanged.connect(
            lambda rect: self.update(rect.translated(-self.offset())))
        track_item.sizeChanged.connect(
            lambda size: self.updateTracks())
        return track_item

    def updateTracks(self):
        self.__content_width = 400
        self.__content_height = 0

        p = QtCore.QPoint(0, 0)
        for track_item in self.tracks():
            track_item.setScaleX(self.__scale_x)
            track_item.setSheetTopLeft(p)
            self.__content_width = max(self.__content_width, track_item.width())
            p += QtCore.QPoint(0, track_item.height())
            p += QtCore.QPoint(0, 3)

        self.__content_height = p.y() + 10

        self.maximumXOffsetChanged.emit(
            max(0, self.__content_width - self.width()))
        self.maximumYOffsetChanged.emit(
            max(0, self.__content_height - self.height()))

        self.update()

    def __onCurrentTrackChanged(self, track):
        if self.__current_track_item is not None:
            self.__current_track_item.currentToolChanged.connect(self.setCurrentTool)

        if track is not None:
            track_item = self.track(track.id)
            self.__current_track_item = track_item

            self.supportedToolsChanged.emit(track_item.supportedTools())
            if self.currentTool() in track_item.supportedTools():
                track_item.setCurrentTool(self.currentTool())
            else:
                self.setCurrentTool(track_item.currentTool())

            track_item.currentToolChanged.connect(self.setCurrentTool)

            self.setCursor(self.currentTool().cursor())

        else:
            self.__current_track_item = None
            self.supportedToolsChanged.emit({tools.Tool.POINTER})
            self.setCurrentTool(tools.Tool.POINTER)

    def maximumXOffset(self):
        return max(0, self.__content_width - self.width())

    def maximumYOffset(self):
        return max(0, self.__content_height - self.height())

    def pageWidth(self):
        return self.width()

    def pageHeight(self):
        return self.height()

    def xOffset(self):
        return self.__x_offset

    def setXOffset(self, offset):
        self.setOffset(offset, self.__y_offset)

    def yOffset(self):
        return self.__y_offset

    def setYOffset(self, offset):
        self.setOffset(self.__x_offset, offset)

    def offset(self):
        return QtCore.QPoint(self.__x_offset, self.__y_offset)

    def setOffset(self, xoffset, yoffset):
        if xoffset == self.__x_offset and yoffset == self.__y_offset:
            return

        dx = self.__x_offset - xoffset
        if dx != 0:
            self.__x_offset = xoffset
            self.xOffsetChanged.emit(self.__x_offset)

        dy = self.__y_offset - yoffset
        if dy != 0:
            self.__y_offset = yoffset
            self.yOffsetChanged.emit(self.__y_offset)

        self.scroll(dx, dy)

    def scaleX(self):
        return self.__scale_x

    def setScaleX(self, scale_x):
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.updateTracks()
        self.scaleXChanged.emit(self.__scale_x)

    def currentTool(self):
        return self.__current_tool

    def setCurrentTool(self, tool):
        assert isinstance(tool, tools.Tool), tool
        if tool != self.__current_tool:
            self.__current_tool = tool
            logger.info("Current tool: %s", tool)

            current_track = self.currentTrack()
            if current_track is not None:
                current_track_item = self.track(current_track.id)
                current_track_item.setCurrentTool(tool)
                self.setCursor(tool.cursor())

            self.currentToolChanged.emit(tool)

    def supportedTools(self):
        for track_item in self.tracks():
            if track_item.isCurrent():
                return track_item.supportedTools()

        return {tools.Tool.POINTER}

    def setPlaybackPos(self, sample_pos, num_samples):
        if not (0 <= sample_pos < self.__time_mapper.total_duration_samples):
            return

        timepos = self.__time_mapper.sample2timepos(sample_pos)
        for track_item in self.tracks():
            track_item.setPlaybackPos(timepos)

    def onPasteAsLink(self):
        if self.selection_set.empty():
            return

        clipboard = self.app.clipboardContent()
        if clipboard['type'] == 'measures':
            self.send_command_async(
                self.__sheet.id, 'PasteMeasuresAsLink',
                src_ids=[copy['id'] for copy in clipboard['data']],
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

        self.maximumXOffsetChanged.emit(
            max(0, self.__content_width - self.width()))
        self.pageWidthChanged.emit(self.width())
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
                evt.localPos() + self.offset() - track_item.sheetTopLeft(),
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
                evt.localPos() + self.offset() - track_item.sheetTopLeft(),
                evt.windowPos(),
                evt.screenPos(),
                evt.button(),
                evt.buttons(),
                evt.modifiers())
            track_item.mouseMoveEvent(track_evt)
            evt.setAccepted(track_evt.isAccepted())
            return

        if track_item is not None and self.currentTool() in track_item.supportedTools():
            self.setCursor(self.currentTool().cursor())
        else:
            self.setCursor(Qt.ArrowCursor)

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
                evt.localPos() + self.offset() - track_item.sheetTopLeft(),
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
                evt.localPos() + self.offset() - self.__mouse_grabber.sheetTopLeft(),
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
                evt.localPos() + self.offset() - track_item.sheetTopLeft(),
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
                evt.pos() + self.offset() - track_item.sheetTopLeft(),
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
            if self.__scale_x > Fraction(10, 1):
                self.setScaleX(self.__scale_x * Fraction(2, 3))
            evt.accept()
            return

        if evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_Right:
            self.setScaleX(self.__scale_x * Fraction(3, 2))
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
                evt.pos() + self.offset() - track_item.sheetTopLeft())
            if not menu.isEmpty():
                menu.exec_(evt.globalPos())
                evt.accept()
                return

    def paintEvent(self, evt):
        super().paintEvent(evt)

        t1 = time.perf_counter()

        painter = QtGui.QPainter(self)

        p = QtCore.QPoint(-self.__x_offset, -self.__y_offset)
        for track_item in self.tracks():
            track_rect = QtCore.QRect(
                0, p.y(), max(self.__content_width, self.width()), track_item.height())
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

        #logger.info("SheetEditor.paintEvent(%s): %.2fµs", evt.rect(), 1e6 * (t2 - t1))


class TimeLine(ui_base.ProjectMixin, QtWidgets.QWidget):
    maximumXOffsetChanged = QtCore.pyqtSignal(int)
    xOffsetChanged = QtCore.pyqtSignal(int)
    pageWidthChanged = QtCore.pyqtSignal(int)

    def __init__(self, *, sheet, sheet_view, player_state, **kwargs):
        super().__init__(**kwargs)

        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)

        self.__sheet = sheet
        self.__sheet_view = sheet_view
        self.__player_state = player_state
        self.__time_mapper = time_mapper.TimeMapper(self.__sheet)
        self.__scale_x = Fraction(500, 1)
        self.__x_offset = 0
        self.__content_width = 200
        self.__player_id = None
        self.__move_timepos = False
        self.__old_player_state = None

        self.__player_state.playbackSamplePosChanged.connect(
            self.onPlaybackSamplePosChanged)
        self.__player_state.loopStartSamplePosChanged.connect(
            lambda _: self.update())
        self.__player_state.loopEndSamplePosChanged.connect(
            lambda _: self.update())

    def setPlayerID(self, player_id):
        self.__player_id = player_id

    def maximumXOffset(self):
        return max(0, self.__content_width - self.width())

    def pageWidth(self):
        return self.width()

    def xOffset(self):
        return self.__x_offset

    def setXOffset(self, offset):
        dx = self.__x_offset - offset
        if dx != 0:
            self.__x_offset = offset
            self.xOffsetChanged.emit(self.__x_offset)
            self.scroll(dx, 0)

    def scaleX(self):
        return self.__scale_x

    def setScaleX(self, scale_x):
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.update()

    def timeposToX(self, timepos):
        x = 10
        for mref in self.__sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if timepos <= measure.duration:
                return x + int(width * timepos / measure.duration)

            x += width
            timepos -= measure.duration

        return x

    def xToTimepos(self, x):
        x -= 10
        timepos = music.Duration(0, 1)
        if x <= 0:
            return timepos

        for mref in self.__sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if x <= width:
                return music.Duration(timepos + measure.duration * music.Duration(int(x), width))

            timepos += measure.duration
            x -= width

        return music.Duration(timepos)

    def onSetLoopStart(self, sample_pos):
        self.call_async(
            self.project_client.player_update_settings(
                self.__player_id,
                music.PlayerSettings(loop_start=sample_pos)))

    def onSetLoopEnd(self, sample_pos):
        self.call_async(
            self.project_client.player_update_settings(
                self.__player_id,
                music.PlayerSettings(loop_end=sample_pos)))

    def onClearLoop(self):
        pass

    def onPlaybackSamplePosChanged(self, sample_pos):
        if self.isVisible():
            x = self.timeposToX(self.__player_state.playbackTimepos())

            left = self.__x_offset + 1 * self.width() / 5
            right = self.__x_offset + 4 * self.width() / 5
            if x < left:
                self.setXOffset(max(0, x - 1 * self.width() / 5))
            elif x > right:
                self.setXOffset(x - 4 * self.width() / 5)

        self.update()

    def mousePressEvent(self, evt):
        if (self.__player_id is not None
            and evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.NoModifier):
            self.__move_timepos = True
            self.__old_player_state = self.__player_state.state()
            x = evt.pos().x() + self.__x_offset
            timepos = self.xToTimepos(x)
            sample_pos = self.__time_mapper.timepos2sample(timepos)
            self.call_async(
                self.project_client.player_update_settings(
                    self.__player_id,
                    music.PlayerSettings(state='stopped')))
            self.__sheet_view.setPlaybackPosMode('manual')
            self.__player_state.setPlaybackSamplePos(sample_pos)
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        if self.__move_timepos:
            x = evt.pos().x() + self.__x_offset
            timepos = self.xToTimepos(x)
            sample_pos = self.__time_mapper.timepos2sample(timepos)
            self.__player_state.setPlaybackSamplePos(sample_pos)
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if (self.__move_timepos
            and evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.NoModifier):
            self.__move_timepos = False
            x = evt.pos().x() + self.__x_offset
            timepos = self.xToTimepos(x)
            sample_pos = self.__time_mapper.timepos2sample(timepos)
            self.call_async(
                self.project_client.player_update_settings(
                    self.__player_id,
                    music.PlayerSettings(
                        state=self.__old_player_state,
                        sample_pos=sample_pos)))
            self.__sheet_view.setPlaybackPosMode('follow')
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()

        if (self.__player_state.state() == 'stopped'
            and self.__player_state.playbackSamplePos() is not None):
            menu.addAction(QtWidgets.QAction(
                "Set loop start", menu,
                triggered=lambda _: self.onSetLoopStart(self.__player_state.playbackSamplePos())))
            menu.addAction(QtWidgets.QAction(
                "Set loop end", menu,
                triggered=lambda _: self.onSetLoopEnd(self.__player_state.playbackSamplePos())))

        menu.addAction(QtWidgets.QAction(
            "Clear loop", menu,
            triggered=lambda _: self.onClearLoop()))

        if not menu.isEmpty():
            menu.exec_(evt.globalPos())
            evt.accept()
            return

    def resizeEvent(self, evt):
        super().resizeEvent(evt)

        self.maximumXOffsetChanged.emit(
            max(0, self.__content_width - self.width()))
        self.pageWidthChanged.emit(self.width())

    def paintEvent(self, evt):
        super().paintEvent(evt)

        painter = QtGui.QPainter(self)
        painter.fillRect(evt.rect(), Qt.white)

        painter.setPen(Qt.black)
        x = 10 - self.__x_offset
        timepos = music.Duration()
        for midx, mref in enumerate(self.__sheet.property_track.measure_list):
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

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

                try:
                    loop_start_timepos = self.__player_state.loopStartTimepos()
                except time_mapper.TimeOutOfRange:
                    pass
                else:
                    if (loop_start_timepos is not None
                            and timepos <= loop_start_timepos < timepos + measure.duration):
                        pos = int(width * (loop_start_timepos - timepos) / measure.duration)
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

                try:
                    loop_end_timepos = self.__player_state.loopEndTimepos()
                except time_mapper.TimeOutOfRange:
                    pass
                else:
                    if (loop_end_timepos is not None
                            and timepos <= loop_end_timepos < timepos + measure.duration):
                        pos = int(width * (loop_end_timepos - timepos) / measure.duration)
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

                try:
                    playback_timepos = self.__player_state.playbackTimepos()
                except time_mapper.TimeOutOfRange:
                    pass
                else:
                    if timepos <= playback_timepos < timepos + measure.duration:
                        pos = int(width * (playback_timepos - timepos) / measure.duration)
                        painter.fillRect(x + pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

            x += width
            timepos += measure.duration

        painter.fillRect(x, 0, 2, self.height(), Qt.black)

        painter.end()


class TrackListItem(ui_base.ProjectMixin, base_track_item.BaseTrackItem):
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
        track_item = TrackListItem(track=track, **self.context)
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


class SheetViewImpl(AsyncSetupBase, QtWidgets.QWidget):
    currentToolChanged = QtCore.pyqtSignal(tools.Tool)
    supportedToolsChanged = QtCore.pyqtSignal(set)
    playbackStateChanged = QtCore.pyqtSignal(str)
    playbackLoopChanged = QtCore.pyqtSignal(bool)

    def __init__(self, sheet, **kwargs):
        super().__init__(**kwargs)

        self.__sheet = sheet
        self.__time_mapper = time_mapper.TimeMapper(self.__sheet)
        self.__player_state = PlayerState(self.__sheet, self.__time_mapper, **self.context)
        self.__player_state.stateChanged.connect(self.playbackStateChanged)
        self.__player_state.loopChanged.connect(self.playbackLoopChanged)

        sheet_editor_frame = Frame(parent=self)
        self.__sheet_editor = SheetEditor(
            sheet=sheet, player_state=self.__player_state,
            parent=sheet_editor_frame, **self.context)
        sheet_editor_frame.setWidget(self.__sheet_editor)

        self.__sheet_editor.currentToolChanged.connect(self.currentToolChanged)
        self.__sheet_editor.supportedToolsChanged.connect(self.supportedToolsChanged)

        time_line_frame = Frame(parent=self)
        self.__time_line = TimeLine(
            sheet=sheet, sheet_view=self, player_state=self.__player_state,
            parent=time_line_frame, **self.context)
        time_line_frame.setWidget(self.__time_line)

        track_list_frame = Frame(parent=self)
        track_list = TrackList(sheet=sheet, parent=track_list_frame, **self.context)
        track_list_frame.setWidget(track_list)

        self.__time_line.setScaleX(self.__sheet_editor.scaleX())
        self.__sheet_editor.scaleXChanged.connect(self.__time_line.setScaleX)

        self.__sheet_editor.currentTrackChanged.connect(track_list.setCurrentTrack)
        track_list.currentTrackChanged.connect(self.__sheet_editor.setCurrentTrack)

        scroll_x = QtWidgets.QScrollBar(orientation=Qt.Horizontal, parent=self)
        scroll_x.setRange(0, self.__sheet_editor.maximumXOffset())
        scroll_x.setSingleStep(50)
        scroll_x.setPageStep(self.__sheet_editor.pageWidth())
        scroll_x.setValue(self.__sheet_editor.xOffset())
        scroll_y = QtWidgets.QScrollBar(orientation=Qt.Vertical, parent=self)
        scroll_y.setRange(0, self.__sheet_editor.maximumYOffset())
        scroll_y.setSingleStep(20)
        scroll_y.setPageStep(self.__sheet_editor.pageHeight())
        scroll_y.setValue(self.__sheet_editor.yOffset())

        self.__sheet_editor.maximumXOffsetChanged.connect(
            scroll_x.setMaximum)
        self.__sheet_editor.pageWidthChanged.connect(
            scroll_x.setPageStep)
        self.__sheet_editor.xOffsetChanged.connect(
            scroll_x.setValue)
        self.__time_line.xOffsetChanged.connect(
            scroll_x.setValue)
        scroll_x.valueChanged.connect(
            self.__sheet_editor.setXOffset)
        scroll_x.valueChanged.connect(
            self.__time_line.setXOffset)

        self.__sheet_editor.maximumYOffsetChanged.connect(
            scroll_y.setMaximum)
        self.__sheet_editor.pageHeightChanged.connect(
            scroll_y.setPageStep)
        self.__sheet_editor.yOffsetChanged.connect(
            scroll_y.setValue)
        scroll_y.valueChanged.connect(
            self.__sheet_editor.setYOffset)
        scroll_y.valueChanged.connect(
            track_list.setYOffset)

        layout = QtWidgets.QGridLayout()
        layout.setSpacing(1)
        layout.addWidget(track_list_frame, 1, 0, 1, 1)
        layout.addWidget(time_line_frame, 0, 1, 1, 1)
        layout.addWidget(sheet_editor_frame, 1, 1, 1, 1)
        layout.addWidget(scroll_x, 2, 0, 1, 2)
        layout.addWidget(scroll_y, 0, 2, 2, 1)
        self.setLayout(layout)

        self.__player_id = None
        self.__player_stream_address = None
        self.__player_node_id = None
        self.__player_status_listener = None
        self.__playback_pos_mode = 'follow'

        self.player_audioproc_address = None

    async def setup(self):
        await super().setup()

        self.__player_id, self.__player_stream_address = await self.project_client.create_player(self.__sheet.id)
        self.__player_status_listener = self.project_client.add_player_status_listener(
            self.__player_id, self.onPlayerStatus)

        self.__time_line.setPlayerID(self.__player_id)
        self.__player_state.setPlayerID(self.__player_id)

        await self.project_client.player_update_settings(
            self.__player_id,
            music.PlayerSettings(
                sample_pos=self.__player_state.playbackSamplePos(),
                loop=self.__player_state.loop(),
                loop_start=self.__player_state.loopStartSamplePos(),
                loop_end=self.__player_state.loopEndSamplePos()))

        self.player_audioproc_address = await self.project_client.get_player_audioproc_address(self.__player_id)

        self.__player_node_id = await self.audioproc_client.add_node(
            'ipc',
            address=self.__player_stream_address,
            event_queue_name='sheet:%s' % self.__sheet.id)
        await self.audioproc_client.connect_ports(
            self.__player_node_id, 'out:left', 'sink', 'in:left')
        await self.audioproc_client.connect_ports(
            self.__player_node_id, 'out:right', 'sink', 'in:right')

    async def cleanup(self):
        await super().cleanup()

        self.__sheet_editor.close()

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

    @property
    def sheet(self):
        return self.__sheet

    def currentTool(self):
        return self.__sheet_editor.currentTool()

    def setCurrentTool(self, tool):
        self.__sheet_editor.setCurrentTool(tool)

    def supportedTools(self):
        return self.__sheet_editor.supportedTools()

    def playbackState(self):
        return self.__player_state.state()

    def playbackLoop(self):
        return self.__player_state.loop()

    def setPlaybackPosMode(self, mode):
        assert mode in ('follow', 'manual')
        self.__playback_pos_mode = mode

    def onPlayerMoveTo(self, where):
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        sample_pos = None

        if where == 'start':
            sample_pos = 0
        elif where == 'end':
            sample_pos = self.__time_mapper.total_duration_samples - 1
        elif where == 'prev':
            timepos = music.Duration()
            prev_timepos = music.Duration()
            for midx, mref in enumerate(self.__sheet.property_track.measure_list):
                measure = mref.measure
                playback_timepos = self.__player_state.playbackTimepos()
                if timepos <= playback_timepos < timepos + measure.duration:
                    if playback_timepos < timepos + music.Duration(1, 16):
                        sample_pos = self.__time_mapper.timepos2sample(prev_timepos)
                    else:
                        sample_pos = self.__time_mapper.timepos2sample(timepos)
                    break

                prev_timepos = timepos
                timepos += measure.duration

        elif where == 'next':
            timepos = music.Duration()
            for midx, mref in enumerate(self.__sheet.property_track.measure_list):
                measure = mref.measure
                playback_timepos = self.__player_state.playbackTimepos()
                if timepos <= playback_timepos < timepos + measure.duration:
                    if midx == len(self.__sheet.property_track.measure_list) - 1:
                        sample_pos = self.__time_mapper.total_duration_samples - 1
                    else:
                        sample_pos = self.__time_mapper.timepos2sample(
                            timepos + measure.duration)
                    break

                timepos += measure.duration

        else:
            raise ValueError(where)

        if sample_pos is not None:
            self.call_async(
                self.project_client.player_update_settings(
                    self.__player_id,
                    music.PlayerSettings(sample_pos=sample_pos)))

    def onPlayerToggle(self):
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        if self.__player_state.state() == 'playing':
            new_state = 'stopped'
        else:
            new_state = 'playing'

        self.call_async(
            self.project_client.player_update_settings(
                self.__player_id,
                music.PlayerSettings(state=new_state)))

    def onPlayerLoop(self, loop):
        if self.__player_id is None:
            logger.warning("Player action without active player.")
            return

        self.call_async(
            self.project_client.player_update_settings(
                self.__player_id,
                music.PlayerSettings(loop=loop)))

    def onPlayerStatus(
            self, playback_pos=None, player_state=None,
            loop=None, loop_start=None, loop_end=None,
            pipeline_state=None, pipeline_disabled=None, **kwargs):
        if playback_pos is not None and self.__playback_pos_mode == 'follow':
            sample_pos, num_samples = playback_pos
            self.__player_state.setPlaybackSamplePos(sample_pos)

        if player_state is not None:
            self.__player_state.setState(player_state)

        if loop is not None:
            self.__player_state.setLoop(loop)

        if loop_start is not None:
            self.__player_state.setLoopStartSamplePos(loop_start)

        if loop_end is not None:
            self.__player_state.setLoopEndSamplePos(loop_end)

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

    def onPasteAsLink(self):
        self.__sheet_editor.onPasteAsLink()


class SheetView(ui_base.ProjectMixin, SheetViewImpl):
    pass
