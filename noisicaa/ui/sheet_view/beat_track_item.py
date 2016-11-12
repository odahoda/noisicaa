#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa import audioproc
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class BeatMeasureEditorItemImpl(base_track_item.MeasureEditorItem):
    FOREGROUND = 'fg'
    BACKGROUND = 'bg'
    GHOST = 'ghost'

    layers = [
        BACKGROUND,
        base_track_item.MeasureEditorItem.PLAYBACK_POS,
        FOREGROUND,
        GHOST,
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__ghost_timepos = None

    def addMeasureListeners(self):
        self.measure_listeners.append(self.measure.listeners.add(
            'beats-changed',
            lambda *args: self.invalidatePaintCache(self.FOREGROUND)))
        self.measure_listeners.append(self.measure.listeners.add(
            'beats',
            lambda *args: self.invalidatePaintCache(self.FOREGROUND)))

    def setGhostTimepos(self, timepos):
        if timepos == self.__ghost_timepos:
            return
        self.__ghost_timepos = timepos
        self.invalidatePaintCache(self.GHOST)

    def paintLayer(self, layer, painter):
        if layer == self.BACKGROUND:
            return self.paintBackground(painter)
        elif layer == self.FOREGROUND:
            return self.paintForeground(painter)
        elif layer == self.GHOST:
            return self.paintGhost(painter)

    def paintBackground(self, painter):
        ymid = self.height() // 2

        painter.setPen(Qt.black)
        painter.drawLine(0, ymid, self.width() - 1, ymid)

        if self.measure is not None:
            painter.drawLine(0, 0, 0, self.height() - 1)

            if self.measure_reference.is_last:
                painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height() - 1)

            for i in range(1, 8 * self.measure.time_signature.upper):
                x = int(i * self.width() / (8 * self.measure.time_signature.upper))
                if i % 8 == 0:
                    h = 10
                elif i % 4 == 0:
                    h = 4
                else:
                    h = 2

                painter.drawLine(x, ymid - h, x, ymid + h)

    def paintForeground(self, painter):
        ymid = self.height() // 2

        for beat in self.measure.beats:
            if not (0 <= beat.timepos < self.measure.duration):
                logger.warning(
                    "Beat outside of measure: %s not in [0,%s)",
                    beat.timepos, self.measure.duration)
                continue

            pos = int(self.width() * beat.timepos / self.measure.duration)

            painter.fillRect(
                pos + 2, ymid + 8, 4, 22 * beat.velocity // 127,
                QtGui.QColor(255, 200, 200))

            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.black)
            polygon = QtGui.QPolygon()
            polygon.append(QtCore.QPoint(pos, ymid - 12))
            polygon.append(QtCore.QPoint(pos, ymid + 12))
            polygon.append(QtCore.QPoint(pos + 8, ymid))
            painter.drawPolygon(polygon)

    def paintGhost(self, painter):
        if self.__ghost_timepos is None:
            return

        ymid = self.height() // 2
        pos = int(self.width() * self.__ghost_timepos / self.measure.duration)

        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        painter.setOpacity(0.4)
        polygon = QtGui.QPolygon()
        polygon.append(QtCore.QPoint(pos, ymid - 12))
        polygon.append(QtCore.QPoint(pos, ymid + 12))
        polygon.append(QtCore.QPoint(pos + 8, ymid))
        painter.drawPolygon(polygon)

    def paintPlaybackPos(self, painter):
        pos = int(
            self.width()
            * self.playbackPos()
            / self.measure.duration)
        painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def leaveEvent(self, evt):
        self.setGhostTimepos(None)
        super().leaveEvent(evt)

    def mouseMoveEvent(self, evt):
        self.setGhostTimepos(music.Duration(
            int(8 * self.measure.time_signature.upper
                * evt.pos().x() / self.width()),
            8 * self.measure.time_signature.upper))
        super().mouseMoveEvent(evt)

    def mousePressEvent(self, evt):
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            click_timepos = music.Duration(
                int(8 * self.measure.time_signature.upper
                    * evt.pos().x() / self.width()),
                8 * self.measure.time_signature.upper)

            for beat in self.measure.beats:
                if beat.timepos == click_timepos:
                    self.send_command_async(
                        self.measure.id, 'RemoveBeat', beat_id=beat.id)
                    evt.accept()
                    return

            self.send_command_async(
                self.measure.id, 'AddBeat', timepos=click_timepos)
            self.track_item.playNoteOn(self.track.pitch)
            evt.accept()
            return

        return super().mousePressEvent(evt)

    def wheelEvent(self, evt):
        if self.measure is not None:
            if evt.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
                if evt.modifiers() == Qt.ShiftModifier:
                    vel_delta = (1 if evt.angleDelta().y() > 0 else -1)
                else:
                    vel_delta = (10 if evt.angleDelta().y() > 0 else -10)

                click_timepos = music.Duration(
                    int(8 * self.measure.time_signature.upper
                        * evt.pos().x() / self.width()),
                    8 * self.measure.time_signature.upper)

                for beat in self.measure.beats:
                    if beat.timepos == click_timepos:
                        self.send_command_async(
                            beat.id, 'SetBeatVelocity',
                            velocity=max(0, min(127, beat.velocity + vel_delta)))
                        evt.accept()
                        return

        return super().wheelEvent(evt)


class BeatMeasureEditorItem(ui_base.ProjectMixin, BeatMeasureEditorItemImpl):
    pass


class BeatTrackEditorItemImpl(base_track_item.MeasuredTrackEditorItem):
    measure_item_cls = BeatMeasureEditorItem

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__play_last_pitch = None

        self.setHeight(60)

    def supportedTools(self):
        return {
            tools.Tool.POINTER,
        }

    def defaultTool(self):
        return tools.Tool.POINTER

    def playNoteOn(self, pitch):
        self.playNoteOff()

        self.call_async(
            self.audioproc_client.add_event(
                'sheet:%s/track:%s' % (
                    self.sheet.id, self.track.id),
                audioproc.NoteOnEvent(-1, pitch)))

        self.__play_last_pitch = pitch

    def playNoteOff(self):
        if self.__play_last_pitch is not None:
            self.call_async(
                self.audioproc_client.add_event(
                    'sheet:%s/track:%s' % (
                        self.sheet.id, self.track.id),
                    audioproc.NoteOffEvent(-1, self.__play_last_pitch)))
            self.__play_last_pitch = None


class BeatTrackEditorItem(ui_base.ProjectMixin, BeatTrackEditorItemImpl):
    pass
