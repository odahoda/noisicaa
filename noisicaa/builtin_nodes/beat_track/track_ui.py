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

import logging
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.ui.track_list import measured_track_editor
from noisicaa.ui.track_list import tools
from noisicaa.builtin_nodes.pianoroll import processor_messages
from . import model

logger = logging.getLogger(__name__)


class EditBeatsTool(measured_track_editor.MeasuredToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.EDIT_BEATS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'edit-beats'

    def mouseMoveMeasureEvent(
            self, measure: measured_track_editor.BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(measure, BeatMeasureEditor), type(measure).__name__
        measure.setGhostTime(measure.xToTime(evt.pos().x()))
        super().mouseMoveMeasureEvent(measure, evt)

    def mousePressMeasureEvent(
            self, measure: measured_track_editor.BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(measure, BeatMeasureEditor), type(measure).__name__

        if (evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier):
            click_time = measure.xToTime(evt.pos().x())

            for beat in measure.measure.beats:
                if beat.time == click_time:
                    with self.project.apply_mutations('%s: Remove beat' % measure.track.name):
                        measure.measure.delete_beat(beat)
                    evt.accept()
                    return

            with self.project.apply_mutations('%s: Insert beat' % measure.track.name):
                measure.measure.create_beat(click_time)
            measure.track_editor.playNoteOn(measure.track.pitch)
            evt.accept()
            return

        super().mousePressMeasureEvent(measure, evt)

    def wheelMeasureEvent(
            self, measure: measured_track_editor.BaseMeasureEditor, evt: QtGui.QWheelEvent) -> None:
        assert isinstance(measure, BeatMeasureEditor), type(measure).__name__

        if evt.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
            if evt.modifiers() == Qt.ShiftModifier:
                vel_delta = (1 if evt.angleDelta().y() > 0 else -1)
            else:
                vel_delta = (10 if evt.angleDelta().y() > 0 else -10)

            click_time = measure.xToTime(evt.pos().x())

            for beat in measure.measure.beats:
                if beat.time == click_time:
                    with self.project.apply_mutations(
                            '%s: Change beat velocity' % measure.track.name):
                        beat.velocity = max(0, min(127, beat.velocity + vel_delta))
                    evt.accept()
                    return

        super().wheelMeasureEvent(measure, evt)


class BeatToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(measured_track_editor.ArrangeMeasuresTool)
        self.addTool(EditBeatsTool)


class BeatMeasureEditor(measured_track_editor.MeasureEditor):
    FOREGROUND = 'fg'
    BACKGROUND = 'bg'
    GHOST = 'ghost'

    layers = [
        BACKGROUND,
        measured_track_editor.MeasureEditor.PLAYBACK_POS,
        FOREGROUND,
        GHOST,
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__ghost_time = None  # type: audioproc.MusicalDuration

    @property
    def track_editor(self) -> 'BeatTrackEditor':
        return down_cast(BeatTrackEditor, super().track_editor)

    @property
    def track(self) -> model.BeatTrack:
        return down_cast(model.BeatTrack, super().track)

    @property
    def measure(self) -> model.BeatMeasure:
        return down_cast(model.BeatMeasure, super().measure)

    def xToTime(self, x: int) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(
            int(8 * self.measure.time_signature.upper * x / self.width()),
            8 * self.measure.time_signature.upper)

    def addMeasureListeners(self) -> None:
        self._measure_listeners.add(self.measure.content_changed.add(
            lambda _=None: self.invalidatePaintCache(self.FOREGROUND)))  # type: ignore[misc]
        self._measure_listeners.add(self.measure.beats_changed.add(
            lambda _: self.invalidatePaintCache(self.FOREGROUND)))

    def setGhostTime(self, time: audioproc.MusicalDuration) -> None:
        if time == self.__ghost_time:
            return
        self.__ghost_time = time
        self.invalidatePaintCache(self.GHOST)

    def paintLayer(self, layer: str, painter: QtGui.QPainter) -> None:
        if layer == self.BACKGROUND:
            return self.paintBackground(painter)
        elif layer == self.FOREGROUND:
            return self.paintForeground(painter)
        elif layer == self.GHOST:
            return self.paintGhost(painter)

    def paintBackground(self, painter: QtGui.QPainter) -> None:
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

    def paintForeground(self, painter: QtGui.QPainter) -> None:
        ymid = self.height() // 2

        for beat in self.measure.beats:
            if not audioproc.MusicalDuration(0, 1) <= beat.time < self.measure.duration:
                logger.warning(
                    "Beat outside of measure: %s not in [0,%s)",
                    beat.time, self.measure.duration)
                continue

            pos = int(self.width() * (beat.time / self.measure.duration).fraction)

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

    def paintGhost(self, painter: QtGui.QPainter) -> None:
        if self.__ghost_time is None:
            return

        ymid = self.height() // 2
        pos = int(self.width() * (self.__ghost_time / self.measure.duration).fraction)

        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        painter.setOpacity(0.4)
        polygon = QtGui.QPolygon()
        polygon.append(QtCore.QPoint(pos, ymid - 12))
        polygon.append(QtCore.QPoint(pos, ymid + 12))
        polygon.append(QtCore.QPoint(pos + 8, ymid))
        painter.drawPolygon(polygon)

    def paintPlaybackPos(self, painter: QtGui.QPainter) -> None:
        pos = int(self.width() * (self.playbackPos() / self.measure.duration).fraction)
        painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setGhostTime(None)
        super().leaveEvent(evt)


class BeatTrackEditor(measured_track_editor.MeasuredTrackEditor):
    measure_type = 'beat'
    measure_editor_cls = BeatMeasureEditor

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__play_last_pitch = None  # type: value_types.Pitch

        self.setDefaultHeight(60)

    @property
    def track(self) -> model.BeatTrack:
        return down_cast(model.BeatTrack, super().track)

    def createToolBox(self) -> BeatToolBox:
        return BeatToolBox(track=self, context=self.context)

    def playNoteOn(self, pitch: value_types.Pitch) -> None:
        self.playNoteOff()

        if self.playerState().playerID():
            self.call_async(self.project_view.sendNodeMessage(
                processor_messages.note_on_event(
                    self.track.pipeline_node_id, 0, pitch.midi_note, 100)))

            self.__play_last_pitch = pitch

    def playNoteOff(self) -> None:
        if self.__play_last_pitch is not None:
            if self.playerState().playerID():
                self.call_async(self.project_view.sendNodeMessage(
                    processor_messages.note_off_event(
                        self.track.pipeline_node_id, 0, self.__play_last_pitch.midi_note)))

            self.__play_last_pitch = None
