#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import music
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item

logger = logging.getLogger(__name__)


class BeatMeasureItemImpl(base_track_item.MeasureItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._ghost_beat = None

        self._layers[base_track_item.Layer.MAIN] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EVENTS] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EDIT] = QGraphicsGroup()

        self.setAcceptHoverEvents(True)

        self._measure_listeners = []

        if self._measure is not None:
            self.addMeasureListeners()

            self.playback_pos = QtWidgets.QGraphicsLineItem(
                self._layers[base_track_item.Layer.EVENTS])
            self.playback_pos.setVisible(False)
            self.playback_pos.setLine(0, 0, 0, 20)
            pen = QtGui.QPen(Qt.black)
            pen.setWidth(3)
            self.playback_pos.setPen(pen)


    def close(self):
        super().close()
        for listener in self._measure_listeners:
            listener.remove()
        self._measure_listeners.clear()

    def addMeasureListeners(self):
        self._measure_listeners.append(self._measure.listeners.add(
            'beats-changed', lambda *args: self.recomputeLayout()))
        self._measure_listeners.append(self._measure.listeners.add(
            'beats', lambda *args: self.recomputeLayout()))

    def measureChanged(self, old_value, new_value):
        super().measureChanged(old_value, new_value)

        for listener in self._measure_listeners:
            listener.remove()
        self._measure_listeners.clear()

        self.addMeasureListeners()

    def getLayout(self):
        if self._measure is not None:
            duration = self._measure.duration
        else:
            duration = music.Duration(2, 4)

        height_above = 30
        height_below = 30

        layout = base_track_item.MeasureLayout(duration)
        layout.height = height_above + height_below
        layout.baseline = height_above
        return layout

    def _updateMeasureInternal(self):
        assert self._layout.width > 0 and self._layout.height > 0

        self._background.setRect(0, 0, self._layout.width, self._layout.height)

        layer = self._layers[base_track_item.Layer.MAIN]
        self._sheet_view.clearLayer(layer)

        is_first = (
            self._measure_reference is not None
            and self._measure_reference.index == 0)

        if self._measure is not None:
            black = Qt.black
        else:
            black = QtGui.QColor(200, 200, 200)

        line = QtWidgets.QGraphicsLineItem(layer)
        line.setLine(0, self._layout.baseline,
                     self._layout.width, self._layout.baseline)
        line.setPen(black)

        if self._measure is not None:
            line = QtWidgets.QGraphicsLineItem(layer)
            line.setLine(0, 0, 0, self._layout.height)
            line.setPen(black)

            if self._measure_reference.is_last:
                line = QtWidgets.QGraphicsLineItem(layer)
                line.setLine(
                    self._layout.width, 0,
                    self._layout.width, self._layout.height)
                line.setPen(black)

            for i in range(1, 8 * self._measure.time_signature.upper):
                x = int(i * self._layout.width / (8 * self._measure.time_signature.upper))
                if i % 8 == 0:
                    h = 10
                elif i % 4 == 0:
                    h = 4
                else:
                    h = 2

                tick = QtWidgets.QGraphicsLineItem(layer)
                tick.setLine(x, self._layout.baseline - h,
                             x, self._layout.baseline + h)
                tick.setPen(black)

            line = QtWidgets.QGraphicsLineItem(layer)
            line.setLine(0, self._layout.baseline - 20,
                         0, self._layout.baseline)
            line.setPen(black)

            if is_first:
                text = QtWidgets.QGraphicsSimpleTextItem(
                    layer)
                text.setText("> %s" % self._measure.track.name)
                text.setPos(0, 0)

            for beat in self._measure.beats:
                assert 0 <= beat.timepos < self._measure.duration

                pos = int(
                    self._layout.width
                    * beat.timepos
                    / self._measure.duration)

                beat_vel = QtWidgets.QGraphicsRectItem(layer)
                beat_vel.setRect(0, 0, 4, 22 * beat.velocity / 127)
                beat_vel.setPen(QtGui.QPen(Qt.NoPen))
                beat_vel.setBrush(QtGui.QColor(255, 200, 200))
                beat_vel.setPos(pos + 2, self._layout.baseline + 8)

                beat_path = QtGui.QPainterPath()
                beat_path.moveTo(0, -12)
                beat_path.lineTo(0, 12)
                beat_path.lineTo(8, 0)
                beat_path.closeSubpath()
                beat_item = QtWidgets.QGraphicsPathItem(layer)
                beat_item.setPath(beat_path)
                beat_item.setPen(QtGui.QPen(Qt.NoPen))
                beat_item.setBrush(black)
                beat_item.setPos(pos, self._layout.baseline)


    def setGhost(self):
        if self._ghost_beat is not None:
            return
        self.removeGhost()

        layer = self._layers[base_track_item.Layer.EDIT]
        self._ghost_beat = QtWidgets.QGraphicsRectItem(layer)
        self._ghost_beat.setRect(0, -30, 8, 50)
        self._ghost_beat.setBrush(Qt.black)
        self._ghost_beat.setPen(QtGui.QPen(Qt.NoPen))
        self._ghost_beat.setOpacity(0.2)

    def removeGhost(self):
        if self._ghost_beat is not None:
            self._ghost_beat.setParentItem(None)
            if self._ghost_beat.scene() is not None:
                self.scene().removeItem(self._ghost_beat)
            self._ghost_beat = None

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        self.grabMouse()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        if not self.boundingRect().contains(event.pos()):
            self._track_item.playNoteOff()
            self._sheet_view.setInfoMessage('')
            self.removeGhost()
            self.ungrabMouse()
            return

        if self._measure is None:
            return

        self.setGhost()

        ghost_timepos = music.Duration(
            int(8 * self._measure.time_signature.upper
                * event.pos().x() / self._layout.width),
            8 * self._measure.time_signature.upper)
        self._ghost_beat.setPos(
            int(self._layout.width * ghost_timepos / self._measure.duration),
            self._layout.baseline)

    def mousePressEvent(self, event):
        if (self._measure is None
                and event.button() == Qt.LeftButton
                and event.modifiers() == Qt.NoModifier):
            self.send_command_async(
                self._sheet_view.sheet.id,
                'InsertMeasure', tracks=[], pos=-1)
            event.accept()
            return

        if self._layout.width <= 0 or self._layout.height <= 0:
            logger.warning("mousePressEvent without valid layout.")
            return

        if (event.button() == Qt.LeftButton
                and event.modifiers() == Qt.NoModifier):
            click_timepos = music.Duration(
                int(8 * self._measure.time_signature.upper
                    * event.pos().x() / self._layout.width),
                8 * self._measure.time_signature.upper)

            for beat in self._measure.beats:
                if beat.timepos == click_timepos:
                    self.send_command_async(
                        self._measure.id, 'RemoveBeat', beat_id=beat.id)
                    event.accept()
                    return

            self.send_command_async(
                self._measure.id, 'AddBeat', timepos=click_timepos)
            self._track_item.playNoteOn(self._measure.track.pitch)
            event.accept()
            return

        return super().mousePressEvent(event)

    def wheelEvent(self, event):
        if self._measure is not None:
            if self._layout.width <= 0 or self._layout.height <= 0:
                logger.warning("mousePressEvent without valid layout.")
                return

            if event.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
                if event.modifiers() == Qt.ShiftModifier:
                    vel_delta = (1 if event.delta() > 0 else -1)
                else:
                    vel_delta = (10 if event.delta() > 0 else -10)

                click_timepos = music.Duration(
                    int(8 * self._measure.time_signature.upper
                        * event.pos().x() / self._layout.width),
                    8 * self._measure.time_signature.upper)

                for beat in self._measure.beats:
                    if beat.timepos == click_timepos:
                        self.send_command_async(
                            beat.id, 'SetBeatVelocity',
                            velocity=max(0, min(127, beat.velocity + vel_delta)))
                        event.accept()
                        return

        return super().wheelEvent(event)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

    def clearPlaybackPos(self):
        self.playback_pos.setVisible(False)

    def setPlaybackPos(
            self, sample_pos, num_samples, start_tick, end_tick, first):
        if first:
            assert 0 <= start_tick < self._measure.duration.ticks
            assert self._layout.width > 0 and self._layout.height > 0

            pos = (
                self._layout.width
                * start_tick
                / self._measure.duration.ticks)
            self.playback_pos.setPos(pos, 0)
            self.playback_pos.setVisible(True)


class BeatMeasureItem(ui_base.ProjectMixin, BeatMeasureItemImpl):
    pass


class BeatTrackItemImpl(base_track_item.MeasuredTrackItemImpl):
    measure_item_cls = BeatMeasureItem

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._play_last_pitch = None

    def playNoteOn(self, pitch):
        self.playNoteOff()

        self.call_async(
            self._sheet_view.audioproc_client.add_event(
                'sheet:%s/track:%s' % (
                    self._sheet_view.sheet.id,
                    self.track.id),
                audioproc.NoteOnEvent(-1, pitch)))

        self._play_last_pitch = pitch

    def playNoteOff(self):
        if self._play_last_pitch is not None:
            self.call_async(
                self._sheet_view.audioproc_client.add_event(
                    'sheet:%s/track:%s' % (
                        self._sheet_view.sheet.id,
                        self.track.id),
                    audioproc.NoteOffEvent(-1, self._play_last_pitch)))
            self._play_last_pitch = None


class BeatTrackItem(ui_base.ProjectMixin, BeatTrackItemImpl):
    pass
