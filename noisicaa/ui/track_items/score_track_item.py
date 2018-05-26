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

import logging
from typing import Any, List, Tuple  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
# TODO: add stubs for QtSvg
from PyQt5 import QtSvg  # type: ignore

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import model
from noisicaa import music
from noisicaa.bindings import lv2
from noisicaa.ui import svg_symbol
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class ScoreToolBase(base_track_item.MeasuredToolBase):
    def __init__(self, *, icon_name: str, hotspot: Tuple[int, int], **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__icon_name = icon_name

        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer = QtSvg.QSvgRenderer(self.iconPath())
        renderer.render(painter, QtCore.QRectF(0, 0, 64, 64))
        painter.end()
        self.__cursor = QtGui.QCursor(pixmap, *hotspot)

    def iconName(self) -> str:
        return self.__icon_name

    def cursor(self) -> QtGui.QCursor:
        return self.__cursor

    def _updateGhost(self, target: 'ScoreMeasureEditorItem', pos: QtCore.QPoint) -> None:
        target.setGhost(None)

    def mouseMoveEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, ScoreMeasureEditorItem), type(target).__name__

        self._updateGhost(target, evt.pos())

        ymid = target.height() // 2
        stave_line = (
            int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line)

        idx, _, _ = target.getEditArea(evt.pos().x())
        if idx < 0:
            self.window.setInfoMessage('')
        else:
            pitch = model.Pitch.name_from_stave_line(
                stave_line, target.measure.key_signature)
            self.window.setInfoMessage(pitch)

        super().mouseMoveEvent(target, evt)


class InsertNoteTool(ScoreToolBase):
    def __init__(self, *, type: tools.ToolType, **kwargs: Any) -> None:  # pylint: disable=redefined-builtin
        super().__init__(
            type=type,
            group=tools.ToolGroup.EDIT,
            icon_name={
                tools.ToolType.NOTE_WHOLE: 'note-whole',
                tools.ToolType.NOTE_HALF: 'note-half',
                tools.ToolType.NOTE_QUARTER: 'note-quarter',
                tools.ToolType.NOTE_8TH: 'note-8th',
                tools.ToolType.NOTE_16TH: 'note-16th',
                tools.ToolType.NOTE_32TH: 'note-32th',
                tools.ToolType.REST_WHOLE: 'rest-whole',
                tools.ToolType.REST_HALF: 'rest-half',
                tools.ToolType.REST_QUARTER: 'rest-quarter',
                tools.ToolType.REST_8TH: 'rest-8th',
                tools.ToolType.REST_16TH: 'rest-16th',
                tools.ToolType.REST_32TH: 'rest-32th',
            }[type],
            hotspot={
                tools.ToolType.NOTE_WHOLE:   (32, 52),
                tools.ToolType.NOTE_HALF:    (32, 52),
                tools.ToolType.NOTE_QUARTER: (32, 52),
                tools.ToolType.NOTE_8TH:     (32, 52),
                tools.ToolType.NOTE_16TH:    (32, 52),
                tools.ToolType.NOTE_32TH:    (32, 52),
                tools.ToolType.REST_WHOLE:   (32, 32),
                tools.ToolType.REST_HALF:    (32, 32),
                tools.ToolType.REST_QUARTER: (32, 32),
                tools.ToolType.REST_8TH:     (32, 32),
                tools.ToolType.REST_16TH:    (32, 32),
                tools.ToolType.REST_32TH:    (32, 32),
            }[type],
            **kwargs)

    def _updateGhost(self, target: 'ScoreMeasureEditorItem', pos: QtCore.QPoint) -> None:
        if pos is None:
            target.setGhost(None)
            return

        ymid = target.height() // 2
        stave_line = int(ymid + 5 - pos.y()) // 10 + target.measure.clef.center_pitch.stave_line

        idx, _, insert_x = target.getEditArea(pos.x())
        if idx < 0:
            target.setGhost(None)
            return

        target.setGhost(
            QtCore.QPoint(
                insert_x,
                ymid - 10 * (stave_line - target.measure.clef.center_pitch.stave_line)))

    def mousePressEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, ScoreMeasureEditorItem), type(target).__name__

        ymid = target.height() // 2
        stave_line = (
            int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line)

        if evt.button() == Qt.LeftButton and (evt.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier:
            if self.type.is_note:
                pitch = model.Pitch.name_from_stave_line(
                    stave_line, target.measure.key_signature)
            else:
                pitch = 'r'

            duration = target.durationForTool(self.type)

            idx, overwrite, _ = target.getEditArea(evt.pos().x())
            if idx >= 0:
                cmd = None
                if evt.modifiers() == Qt.ShiftModifier:
                    if overwrite:
                        if len(target.measure.notes[idx].pitches) > 1:
                            for pitch_idx, p in enumerate(target.measure.notes[idx].pitches):
                                if p.stave_line == stave_line:
                                    cmd = music.Command(
                                        target=target.measure.id,
                                        remove_pitch=music.RemovePitch(
                                            idx=idx,
                                            pitch_idx=pitch_idx))
                                    break
                        else:
                            cmd = music.Command(
                                target=target.measure.id,
                                delete_note=music.DeleteNote(idx=idx))
                else:
                    if overwrite:
                        for pitch_idx, p in enumerate(target.measure.notes[idx].pitches):
                            if p.stave_line == stave_line:
                                break
                        else:
                            cmd = music.Command(
                                target=target.measure.id,
                                add_pitch=music.AddPitch(idx=idx, pitch=pitch))
                            target.track_item.playNoteOn(model.Pitch(pitch))
                    else:
                        cmd = music.Command(
                            target=target.measure.id,
                            insert_note=music.InsertNote(
                                idx=idx, pitch=pitch, duration=duration.to_proto()))
                        target.track_item.playNoteOn(model.Pitch(pitch))

                if cmd is not None:
                    self.send_command_async(cmd)
                    evt.accept()
                    return

        super().mousePressEvent(target, evt)

    def mouseReleaseEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, ScoreMeasureEditorItem), type(target).__name__

        target.track_item.playNoteOff()
        return super().mouseReleaseEvent(target, evt)


class ModifyNoteTool(ScoreToolBase):
    def __init__(self, *, type: tools.ToolType, **kwargs: Any) -> None:  # pylint: disable=redefined-builtin
        super().__init__(
            type=type,
            group=tools.ToolGroup.EDIT,
            icon_name={
                tools.ToolType.ACCIDENTAL_NATURAL: 'accidental-natural',
                tools.ToolType.ACCIDENTAL_SHARP: 'accidental-sharp',
                tools.ToolType.ACCIDENTAL_FLAT: 'accidental-flat',
                tools.ToolType.ACCIDENTAL_DOUBLE_SHARP: 'accidental-double-sharp',
                tools.ToolType.ACCIDENTAL_DOUBLE_FLAT: 'accidental-double-flat',
                tools.ToolType.DURATION_DOT: 'duration-dot',
                tools.ToolType.DURATION_TRIPLET: 'duration-triplet',
                tools.ToolType.DURATION_QUINTUPLET: 'duration-quintuplet',
            }[type],
            hotspot={
                tools.ToolType.ACCIDENTAL_NATURAL:      (32, 32),
                tools.ToolType.ACCIDENTAL_SHARP:        (32, 32),
                tools.ToolType.ACCIDENTAL_FLAT:         (32, 39),
                tools.ToolType.ACCIDENTAL_DOUBLE_SHARP: (32, 32),
                tools.ToolType.ACCIDENTAL_DOUBLE_FLAT:  (32, 32),
                tools.ToolType.DURATION_DOT:        (32, 52),
                tools.ToolType.DURATION_TRIPLET:    (32, 32),
                tools.ToolType.DURATION_QUINTUPLET: (32, 32),
            }[type],
            **kwargs)

    def _updateGhost(self, target: 'ScoreMeasureEditorItem', pos: QtCore.QPoint) -> None:
        if pos is None:
            target.setGhost(None)
            return

        ymid = target.height() // 2
        stave_line = int(ymid + 5 - pos.y()) // 10 + target.measure.clef.center_pitch.stave_line

        idx, _, insert_x = target.getEditArea(pos.x())
        if idx < 0:
            target.setGhost(None)
            return

        target.setGhost(
            QtCore.QPoint(
                insert_x - 12,
                ymid - 10 * (stave_line - target.measure.clef.center_pitch.stave_line)))

    def mousePressEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, ScoreMeasureEditorItem), type(target).__name__
        ymid = target.height() // 2
        stave_line = (
            int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line)

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self.type.is_accidental):
            idx, overwrite, _ = target.getEditArea(evt.pos().x())
            if idx >= 0 and overwrite:
                accidental = {
                    tools.ToolType.ACCIDENTAL_NATURAL: '',
                    tools.ToolType.ACCIDENTAL_FLAT: 'b',
                    tools.ToolType.ACCIDENTAL_SHARP: '#',
                    tools.ToolType.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                    tools.ToolType.ACCIDENTAL_DOUBLE_SHARP: '##',
                }[self.type]
                for pitch_idx, p in enumerate(target.measure.notes[idx].pitches):
                    if accidental in p.valid_accidentals:
                        if p.stave_line == stave_line:
                            self.send_command_async(music.Command(
                                target.measure.id,
                                set_accidental=music.SetAccidental(
                                    idx=idx, accidental=accidental,
                                    pitch_idx=pitch_idx)))
                            evt.accept()
                            return


        if (evt.button() == Qt.LeftButton
                and (evt.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
                and self.type.is_duration):
            idx, overwrite, _ = target.getEditArea(evt.pos().x())
            if idx >= 0 and overwrite:
                note = target.measure.notes[idx]
                cmd = None
                if self.type == tools.ToolType.DURATION_DOT:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.dots > 0:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, dots=note.dots - 1))
                    else:
                        if note.dots < note.max_allowed_dots:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, dots=note.dots + 1))

                elif self.type == tools.ToolType.DURATION_TRIPLET:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 3:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, tuplet=3))

                elif self.type == tools.ToolType.DURATION_QUINTUPLET:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 5:
                            cmd = music.Command(
                                target=target.measure.id,
                                change_note=music.ChangeNote(
                                    idx=idx, tuplet=5))

                if cmd is not None:
                    self.send_command_async(cmd)
                    evt.accept()
                    return

        return super().mousePressEvent(target, evt)


class ScoreToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(base_track_item.ArrangeMeasuresTool(context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_WHOLE, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_HALF, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_QUARTER, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_8TH, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_16TH, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_32TH, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_WHOLE, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_HALF, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_QUARTER, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_8TH, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_16TH, context=self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_32TH, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_NATURAL, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_SHARP, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_FLAT, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_DOT, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_TRIPLET, context=self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_QUINTUPLET, context=self.context))

    def keyPressEvent(self, target: Any, evt: QtGui.QKeyEvent) -> None:
        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_Period):
            self.setCurrentToolType(tools.ToolType.DURATION_DOT)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_F):
            self.setCurrentToolType(tools.ToolType.ACCIDENTAL_FLAT)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_S):
            self.setCurrentToolType(tools.ToolType.ACCIDENTAL_SHARP)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_N):
            self.setCurrentToolType(tools.ToolType.ACCIDENTAL_NATURAL)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_R):
            self.setCurrentToolType({
                tools.ToolType.NOTE_WHOLE: tools.ToolType.REST_WHOLE,
                tools.ToolType.NOTE_HALF: tools.ToolType.REST_HALF,
                tools.ToolType.NOTE_QUARTER: tools.ToolType.REST_QUARTER,
                tools.ToolType.NOTE_8TH: tools.ToolType.REST_8TH,
                tools.ToolType.NOTE_16TH: tools.ToolType.REST_16TH,
                tools.ToolType.NOTE_32TH: tools.ToolType.REST_32TH,
                tools.ToolType.REST_WHOLE: tools.ToolType.NOTE_WHOLE,
                tools.ToolType.REST_HALF: tools.ToolType.NOTE_HALF,
                tools.ToolType.REST_QUARTER: tools.ToolType.NOTE_QUARTER,
                tools.ToolType.REST_8TH: tools.ToolType.NOTE_8TH,
                tools.ToolType.REST_16TH: tools.ToolType.NOTE_16TH,
                tools.ToolType.REST_32TH: tools.ToolType.NOTE_32TH,
            }.get(self.currentToolType(), tools.ToolType.REST_QUARTER))
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_1):
            self.setCurrentToolType(
                tools.ToolType.NOTE_WHOLE
                if not self.currentToolType().is_rest
                else tools.ToolType.REST_WHOLE)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_2):
            self.setCurrentToolType(
                tools.ToolType.NOTE_HALF
                if not self.currentToolType().is_rest
                else tools.ToolType.REST_HALF)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_3):
            self.setCurrentToolType(
                tools.ToolType.NOTE_QUARTER
                if not self.currentToolType().is_rest
                else tools.ToolType.REST_QUARTER)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_4):
            self.setCurrentToolType(
                tools.ToolType.NOTE_8TH if
                not self.currentToolType().is_rest
                else tools.ToolType.REST_8TH)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_5):
            self.setCurrentToolType(
                tools.ToolType.NOTE_16TH
                if not self.currentToolType().is_rest
                else tools.ToolType.REST_16TH)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_6):
            self.setCurrentToolType(
                tools.ToolType.NOTE_32TH
                if not self.currentToolType().is_rest
                else tools.ToolType.REST_32TH)

            evt.accept()
            return

        super().keyPressEvent(target, evt)

    def keyReleaseEvent(self, target: Any, evt: QtGui.QKeyEvent) -> None:
        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_Period):
            self.setPreviousTool()
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_F):
            self.setPreviousTool()
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_S):
            self.setPreviousTool()
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_N):
            self.setPreviousTool()
            evt.accept()
            return

        super().keyReleaseEvent(target, evt)

    # def keyPressEvent(self, evt):
    #     if (evt.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
    #             and evt.key() == Qt.Key_Up):
    #         self._transpose_octave_up_action.trigger()
    #         evt.accept()
    #         return

    #     if (evt.modifiers() == Qt.ControlModifier
    #             and evt.key() == Qt.Key_Up):
    #         self._transpose_halfnote_up_action.trigger()
    #         evt.accept()
    #         return

    #     if (evt.modifiers() == Qt.ControlModifier
    #             and evt.key() == Qt.Key_Down):
    #         self._transpose_halfnote_down_action.trigger()
    #         evt.accept()
    #         return

    #     if (evt.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
    #             and evt.key() == Qt.Key_Down):
    #         self._transpose_octave_down_action.trigger()
    #         evt.accept()
    #         return

    #     super().keyPressEvent(evt)


class ScoreMeasureEditorItem(base_track_item.MeasureEditorItem):
    FOREGROUND = 'fg'
    BACKGROUND = 'bg'
    GHOST = 'ghost'

    layers = [
        BACKGROUND,
        base_track_item.MeasureEditorItem.PLAYBACK_POS,
        FOREGROUND,
        GHOST,
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._edit_areas = []  # type: List[Tuple[int, int, int, bool]]
        self._note_area = None  # type: Tuple[int, int]
        self.__mouse_pos = None  # type: QtCore.QPoint
        self.__ghost_pos = None  # type: QtCore.QPoint

        self.track_item.currentToolChanged.connect(
            lambda _: self.updateGhost(self.__mouse_pos))

    @property
    def track(self) -> music.ScoreTrack:
        return down_cast(music.ScoreTrack, super().track)

    @property
    def measure(self) -> music.ScoreMeasure:
        return down_cast(music.ScoreMeasure, super().measure)

    _accidental_map = {
        '': 'accidental-natural',
        '#': 'accidental-sharp',
        'b': 'accidental-flat',
        '##': 'accidental-double-sharp',
        'bb': 'accidental-double-flat',
    }

    def addMeasureListeners(self) -> None:
        self.measure_listeners.append(self.measure.listeners.add(
            'notes-changed',
            lambda *args: self.invalidatePaintCache(self.FOREGROUND)))
        self.measure_listeners.append(self.measure.listeners.add(
            'clef', self.onClefChanged))
        self.measure_listeners.append(self.measure.listeners.add(
            'key_signature', self.onKeySignatureChanged))

    def onClefChanged(self, old_value: model.Clef, new_value: model.Clef) -> None:
        self.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)
        self.next_sibling.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)

    def onKeySignatureChanged(
            self, old_value: model.KeySignature, new_value: model.KeySignature) -> None:
        self.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)
        self.next_sibling.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)

    def paintLayer(self, layer: str, painter: QtGui.QPainter) -> None:
        if layer == self.BACKGROUND:
            self.paintBackground(painter)
        elif layer == self.FOREGROUND:
            self.paintForeground(painter)
        elif layer == self.GHOST:
            self.paintGhost(painter)

    def paintBackground(self, painter: QtGui.QPainter) -> None:
        ymid = self.height() // 2

        painter.setPen(Qt.black)
        painter.setBrush(Qt.black)

        for l in range(-2, 3):
            painter.drawLine(0, ymid + 20 * l, self.width() - 1, ymid + 20 * l)

        if self.is_first:
            painter.fillRect(0, ymid - 40, 2, 20 * 4, Qt.black)

        painter.drawLine(self.width() - 1, ymid - 40, self.width() - 1, ymid + 40)

        base_stave_line = self.measure.clef.center_pitch.stave_line
        base_octave = self.measure.clef.base_octave
        x = 0

        paint_clef = (
            self.measure_reference.is_first
            or (self.measure.clef
                != down_cast(music.ScoreMeasure, self.measure_reference.prev_sibling.measure).clef))

        if paint_clef and self.width() - x > 200:
            svg_symbol.paintSymbol(
                painter,
                'clef-%s' % self.measure.clef.symbol,
                QtCore.QPoint(
                    x + 30,
                    ymid - 10 * (self.measure.clef.base_pitch.stave_line - base_stave_line)))
            x += 60

        acc_map = {
            'C#': 'C%d' % (base_octave + 1),
            'D#': 'D%d' % (base_octave + 1),
            'E#': 'E%d' % (base_octave + 1),
            'F#': 'F%d' % (base_octave + 1),
            'G#': 'G%d' % (base_octave + 1),
            'A#': 'A%d' % base_octave,
            'B#': 'B%d' % base_octave,
            'Cb': 'C%d' % (base_octave + 1),
            'Db': 'D%d' % (base_octave + 1),
            'Eb': 'E%d' % (base_octave + 1),
            'Fb': 'F%d' % base_octave,
            'Gb': 'G%d' % base_octave,
            'Ab': 'A%d' % base_octave,
            'Bb': 'B%d' % base_octave,
        }

        paint_key_signature = (
            self.measure_reference.is_first
            or (self.measure.key_signature != down_cast(
                music.ScoreMeasure, self.measure_reference.prev_sibling.measure).key_signature))

        if paint_key_signature and self.width() - x > 200:
            for acc in self.measure.key_signature.accidentals:
                value = acc_map[acc]
                stave_line = model.Pitch(value).stave_line - base_stave_line

                svg_symbol.paintSymbol(
                    painter,
                    self._accidental_map[acc[1:]],
                    QtCore.QPoint(
                        x + 10,
                        ymid - 10 * stave_line))

                x += 10

            if self.measure.key_signature.accidentals:
                x += 10

        paint_time_signature = (
            self.measure_reference.is_first
            or (self.measure.time_signature != down_cast(
                music.ScoreMeasure, self.measure_reference.prev_sibling.measure).time_signature))

        if paint_time_signature and self.width() - x > 200:
            font = QtGui.QFont('FreeSerif', 30, QtGui.QFont.Black)
            font.setStretch(120)
            painter.setFont(font)

            painter.drawText(
                x, ymid - 5, '%d' % self.measure.time_signature.upper)
            painter.drawText(
                x, ymid + 32, '%d' % self.measure.time_signature.lower)

            x += 40

        if self.width() - x > 100:
            self._note_area = (x + 20, self.width() - x - 20)

        else:
            self._note_area = (0, self.width())

    def paintForeground(self, painter: QtGui.QPainter) -> None:
        assert self._note_area is not None
        self._edit_areas.clear()

        ymid = self.height() // 2

        base_stave_line = self.measure.clef.center_pitch.stave_line
        base_octave = self.measure.clef.base_octave

        acc_map = {
            'C#': 'C%d' % (base_octave + 1),
            'D#': 'D%d' % (base_octave + 1),
            'E#': 'E%d' % (base_octave + 1),
            'F#': 'F%d' % (base_octave + 1),
            'G#': 'G%d' % (base_octave + 1),
            'A#': 'A%d' % base_octave,
            'B#': 'B%d' % base_octave,
            'Cb': 'C%d' % (base_octave + 1),
            'Db': 'D%d' % (base_octave + 1),
            'Eb': 'E%d' % (base_octave + 1),
            'Fb': 'F%d' % base_octave,
            'Gb': 'G%d' % base_octave,
            'Ab': 'A%d' % base_octave,
            'Bb': 'B%d' % base_octave,
        }

        active_accidentals = {}
        for acc in self.measure.key_signature.accidentals:
            value = acc_map[acc]
            active_accidentals[value[:1]] = acc[1:]

        x, note_area_width = self._note_area
        if note_area_width > 80:
            px = x - 20
            note_time = audioproc.MusicalDuration(0)
            for idx, note in enumerate(self.measure.notes):
                overflow = note_time + note.duration > self.measure.duration

                if note.is_rest:
                    sym = {
                        1: 'rest-whole',
                        2: 'rest-half',
                        4: 'rest-quarter',
                        8: 'rest-8th',
                        16: 'rest-16th',
                        32: 'rest-32th',
                    }[note.base_duration.denominator]
                    svg_symbol.paintSymbol(
                        painter, sym, QtCore.QPoint(x, ymid))

                    if note.base_duration >= audioproc.MusicalDuration(1, 2):
                        dx = 25
                        dy = -10
                    else:
                        dx = 12
                        dy = 0

                    for d in range(note.dots):
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(Qt.black)
                        painter.drawEllipse(dx - 4 + 10*d, dy - 4, 9, 9)

                    if note.tuplet != 0:
                        painter.setPen(Qt.black)
                        painter.drawText(-5, -45, '%d' % note.tuplet)

                    # if overflow:
                    #     n.setOpacity(0.4)
                elif len(note.pitches) > 0:
                    min_stave_line = 1000
                    max_stave_line = -1000

                    for pitch in note.pitches:
                        stave_line = pitch.stave_line - base_stave_line
                        min_stave_line = min(min_stave_line, stave_line)
                        max_stave_line = max(max_stave_line, stave_line)

                    painter.setPen(Qt.black)
                    painter.setOpacity(0.4 if overflow else 0.8)

                    # Ledger lines above stave.
                    for l in range(6, max_stave_line + 1, 2):
                        painter.drawLine(
                            x - 20, ymid - 10 * l,
                            x + 20, ymid - 10 * l)

                    # Ledger lines below stave.
                    for l in range(-6, min_stave_line - 1, -2):
                        painter.drawLine(
                            x - 20, ymid - 10 * l,
                            x + 20, ymid - 10 * l)

                    painter.setOpacity(1.0)

                    for pitch in note.pitches:
                        stave_line = pitch.stave_line - base_stave_line

                        y = ymid - 10 * stave_line

                        active_accidental = active_accidentals.get(pitch.value, '')
                        if pitch.accidental != active_accidental:
                            sym = self._accidental_map[pitch.accidental]
                            svg_symbol.paintSymbol(
                                painter, sym,
                                QtCore.QPoint(x - 12, y))
                            active_accidentals[pitch.value] = pitch.accidental

                        if note.base_duration >= audioproc.MusicalDuration(1, 2):
                            svg_symbol.paintSymbol(
                                painter, 'note-head-void', QtCore.QPoint(x, y))
                        else:
                            svg_symbol.paintSymbol(
                                painter, 'note-head-black', QtCore.QPoint(x, y))

                        if note.base_duration <= audioproc.MusicalDuration(1, 2):
                            painter.fillRect(x + 8, y - 63, 3, 60, Qt.black)

                        if note.base_duration == audioproc.MusicalDuration(1, 8):
                            flags = 1
                        elif note.base_duration == audioproc.MusicalDuration(1, 16):
                            flags = 2
                        elif note.base_duration == audioproc.MusicalDuration(1, 32):
                            flags = 3
                        else:
                            flags = 0

                        for f in range(flags):
                            svg_symbol.paintSymbol(
                                painter, 'note-flag-down',
                                QtCore.QPoint(x + 11, y - 63 + 12 * f))

                        for d in range(note.dots):
                            painter.setPen(Qt.NoPen)
                            painter.setBrush(Qt.black)
                            painter.drawEllipse(x + 12 + 10*d, y - 4, 9, 9)

                        if note.tuplet != 0:
                            painter.drawText(x - 5, y - 85, '%d' % note.tuplet)

                    # if overflow:
                    #     n.setOpacity(0.4)

                    # if self.app.showEditAreas:
                    #     info = QtWidgets.QGraphicsSimpleTextItem(self)
                    #     info.setText(
                    #         '%d/%d' % (min_stave_line, max_stave_line))
                    #     info.setPos(x - 10, 0)

                x1 = max(x - 12, px)
                x2 = max(x + 13, x1)
                if x1 > px:
                    self._edit_areas.append((px, x1, idx, False))
                    px = x1
                if x2 > x1:
                    self._edit_areas.append((x1, x2, idx, True))
                    px = x2

                note_time += note.duration
                x += int(note_area_width * note.duration.fraction)

            if px < self.width():
                self._edit_areas.append(
                    (px, self.width(), len(self.measure.notes), False))
        else:
            self._note_area = (0, self.width())

    def paintGhost(self, painter: QtGui.QPainter) -> None:
        if self.__ghost_pos is None:
            return

        ymid = self.height() // 2

        tool = self.track_item.currentToolType()
        pos = self.__ghost_pos
        painter.setOpacity(0.4)

        if tool.is_rest:
            sym = {
                1: 'rest-whole',
                2: 'rest-half',
                4: 'rest-quarter',
                8: 'rest-8th',
                16: 'rest-16th',
                32: 'rest-32th',
            }[self._tool_duration_map[tool].denominator]
            svg_symbol.paintSymbol(
                painter, sym, QtCore.QPoint(pos.x(), ymid))

        elif tool.is_note:
            duration = self._tool_duration_map[tool]

            if duration >= audioproc.MusicalDuration(1, 2):
                svg_symbol.paintSymbol(
                    painter, 'note-head-void', pos)
            else:
                svg_symbol.paintSymbol(
                    painter, 'note-head-black', pos)

            if duration <= audioproc.MusicalDuration(1, 2):
                painter.fillRect(pos.x() + 8, pos.y() - 63, 3, 60, Qt.black)

            if duration == audioproc.MusicalDuration(1, 8):
                flags = 1
            elif duration == audioproc.MusicalDuration(1, 16):
                flags = 2
            elif duration == audioproc.MusicalDuration(1, 32):
                flags = 3
            else:
                flags = 0

            for f in range(flags):
                svg_symbol.paintSymbol(
                    painter, 'note-flag-down',
                    QtCore.QPoint(pos.x() + 11, pos.y() - 63 + 12 * f))

        elif tool.is_accidental:
            accidental = {
                tools.ToolType.ACCIDENTAL_NATURAL: '',
                tools.ToolType.ACCIDENTAL_FLAT: 'b',
                tools.ToolType.ACCIDENTAL_SHARP: '#',
                tools.ToolType.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                tools.ToolType.ACCIDENTAL_DOUBLE_SHARP: '##',
            }[tool]
            sym = self._accidental_map[accidental]
            svg_symbol.paintSymbol(painter, sym, pos)

        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.black)
            painter.drawEllipse(pos.x() - 15, pos.y() - 15, 31, 31)

    def paintPlaybackPos(self, painter: QtGui.QPainter) -> None:
        assert self._note_area is not None

        left, width = self._note_area
        pos = left + int(width * (self.playbackPos() / self.measure.duration).fraction)
        painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def getEditArea(self, x: int) -> Tuple[int, bool, int]:
        for x1, x2, idx, overwrite in self._edit_areas:
            if x1 < x <= x2:
                return idx, overwrite, (x1 + x2) // 2
        return -1, False, 0

    _tool_duration_map = {
        tools.ToolType.NOTE_WHOLE:   audioproc.MusicalDuration(1, 1),
        tools.ToolType.NOTE_HALF:    audioproc.MusicalDuration(1, 2),
        tools.ToolType.NOTE_QUARTER: audioproc.MusicalDuration(1, 4),
        tools.ToolType.NOTE_8TH:     audioproc.MusicalDuration(1, 8),
        tools.ToolType.NOTE_16TH:    audioproc.MusicalDuration(1, 16),
        tools.ToolType.NOTE_32TH:    audioproc.MusicalDuration(1, 32),

        tools.ToolType.REST_WHOLE:   audioproc.MusicalDuration(1, 1),
        tools.ToolType.REST_HALF:    audioproc.MusicalDuration(1, 2),
        tools.ToolType.REST_QUARTER: audioproc.MusicalDuration(1, 4),
        tools.ToolType.REST_8TH:     audioproc.MusicalDuration(1, 8),
        tools.ToolType.REST_16TH:    audioproc.MusicalDuration(1, 16),
        tools.ToolType.REST_32TH:    audioproc.MusicalDuration(1, 32),
    }

    def durationForTool(self, tool: tools.ToolType) -> audioproc.MusicalDuration:
        assert tool.is_note or tool.is_rest
        return self._tool_duration_map[tool]

    def setGhost(self, pos: QtCore.QPoint) -> None:
        if pos == self.__ghost_pos:
            return

        self.__ghost_pos = pos
        self.invalidatePaintCache(self.GHOST)

    def updateGhost(self, pos: QtCore.QPoint) -> None:
        if pos is None:
            self.setGhost(None)
            return

        ymid = self.height() // 2
        stave_line = int(ymid + 5 - pos.y()) // 10 + self.measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = self.getEditArea(pos.x())
        if idx < 0:
            self.setGhost(None)
            return

        tool = self.track_item.currentToolType()
        if tool.is_note or tool.is_rest:
            self.setGhost(
                QtCore.QPoint(
                    insert_x,
                    ymid - 10 * (stave_line - self.measure.clef.center_pitch.stave_line)))

        elif tool.is_accidental and overwrite:
            self.setGhost(
                QtCore.QPoint(
                    insert_x - 12,
                    ymid - 10 * (stave_line - self.measure.clef.center_pitch.stave_line)))

        else:
            self.setGhost(None)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.__mouse_pos = None
        self.setGhost(None)
        super().leaveEvent(evt)


class ScoreTrackEditorItem(base_track_item.MeasuredTrackEditorItem):
    measure_item_cls = ScoreMeasureEditorItem

    toolBoxClass = ScoreToolBox

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__play_last_pitch = None  # type: model.Pitch

        self.setHeight(240)

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        super().buildContextMenu(menu, pos)

        affected_measure_items = []  # type: List[ScoreMeasureEditorItem]
        if not self.selection_set.empty():
            affected_measure_items.extend(
                down_cast(ScoreMeasureEditorItem, sitem) for sitem in self.selection_set)
        else:
            mitem = self.measureItemAt(pos)
            if isinstance(mitem, ScoreMeasureEditorItem):
                affected_measure_items.append(mitem)

        enable_measure_actions = bool(affected_measure_items)

        clef_menu = menu.addMenu("Set clef")
        for clef in model.Clef:
            clef_action = QtWidgets.QAction(clef.value, menu)
            clef_action.setEnabled(enable_measure_actions)
            clef_action.triggered.connect(
                lambda _, clef=clef: self.onSetClef(affected_measure_items, clef))
            clef_menu.addAction(clef_action)

        key_signature_menu = menu.addMenu("Set key signature")
        key_signatures = [
            'C major',
            'A minor',
            'G major',
            'E minor',
            'D major',
            'B minor',
            'A major',
            'F# minor',
            'E major',
            'C# minor',
            'B major',
            'G# minor',
            'F# major',
            'D# minor',
            'C# major',
            'A# minor',
            'F major',
            'D minor',
            'Bb major',
            'G minor',
            'Eb major',
            'C minor',
            'Ab major',
            'F minor',
            'Db major',
            'Bb minor',
            'Gb major',
            'Eb minor',
            'Cb major',
            'Ab minor',
        ]
        for key_signature in key_signatures:
            key_signature_action = QtWidgets.QAction(key_signature, menu)
            key_signature_action.setEnabled(enable_measure_actions)
            key_signature_action.triggered.connect(
                lambda _, sig=key_signature: self.onSetKeySignature(affected_measure_items, sig))
            key_signature_menu.addAction(key_signature_action)

        time_signature_menu = menu.addMenu("Set time signature")
        time_signatures = [
            (4, 4),
            (3, 4),
        ]
        for upper, lower in time_signatures:
            time_signature_action = QtWidgets.QAction("%d/%d" % (upper, lower), menu)
            time_signature_action.setEnabled(enable_measure_actions)
            time_signature_action.triggered.connect(
                lambda _, upper=upper, lower=lower: (
                    self.onSetTimeSignature(affected_measure_items, upper, lower)))
            time_signature_menu.addAction(time_signature_action)

        transpose_menu = menu.addMenu("Transpose")

        octave_up_action = QtWidgets.QAction("Octave up", self)
        octave_up_action.setEnabled(enable_measure_actions)
        octave_up_action.setShortcut('Ctrl+Shift+Up')
        octave_up_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        octave_up_action.triggered.connect(lambda _: self.onTranspose(affected_measure_items, 12))
        transpose_menu.addAction(octave_up_action)

        halfnote_up_action = QtWidgets.QAction("Half-note up", self)
        halfnote_up_action.setEnabled(enable_measure_actions)
        halfnote_up_action.setShortcut('Ctrl+Up')
        halfnote_up_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        halfnote_up_action.triggered.connect(lambda _: self.onTranspose(affected_measure_items, 1))
        transpose_menu.addAction(halfnote_up_action)

        halfnote_down_action = QtWidgets.QAction("Half-note down", self)
        halfnote_down_action.setEnabled(enable_measure_actions)
        halfnote_down_action.setShortcut('Ctrl+Down')
        halfnote_down_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        halfnote_down_action.triggered.connect(
            lambda _: self.onTranspose(affected_measure_items, -1))
        transpose_menu.addAction(halfnote_down_action)

        octave_down_action = QtWidgets.QAction("Octave down", self)
        octave_down_action.setEnabled(enable_measure_actions)
        octave_down_action.setShortcut('Ctrl+Shift+Down')
        octave_down_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        octave_down_action.triggered.connect(
            lambda _: self.onTranspose(affected_measure_items, -12))
        transpose_menu.addAction(octave_down_action)

    def onSetClef(
            self, affected_measure_items: List[ScoreMeasureEditorItem], clef: model.Clef) -> None:
        self.send_command_async(music.Command(
            target=self.track.id,
            set_clef=music.SetClef(
                measure_ids=[mitem.measure.id for mitem in affected_measure_items],
                clef=clef.value)))

    def onSetKeySignature(
            self, affected_measure_items: List[ScoreMeasureEditorItem],
            key_signature: model.KeySignature) -> None:
        self.send_command_async(music.Command(
            target=self.track.id,
            set_key_signature=music.SetKeySignature(
                measure_ids=[mitem.measure.id for mitem in affected_measure_items],
                key_signature=key_signature.to_proto())))

    def onSetTimeSignature(
            self, affected_measure_items: List[ScoreMeasureEditorItem], upper: int, lower: int
    ) -> None:
        self.send_command_async(music.Command(
            target=self.property_track.id,
            set_time_signature=music.SetTimeSignature(
                measure_ids=[
                    self.property_track.measure_list[mitem.measure_reference.index].measure.id
                    for mitem in affected_measure_items],
                upper=upper, lower=lower)))

    def onTranspose(
            self, affected_measure_items: List[ScoreMeasureEditorItem], half_notes: int) -> None:
        note_ids = set()
        for mitem in affected_measure_items:
            for note in mitem.measure.notes:
                note_ids.add(note.id)

        self.send_command_async(music.Command(
            target=self.track.id,
            transpose_notes=music.TransposeNotes(
                note_ids=list(note_ids),
                half_notes=half_notes)))

    def playNoteOn(self, pitch: model.Pitch) -> None:
        self.playNoteOff()

        if self.playerState().playerID():
            self.call_async(
                self.project_client.player_send_message(
                    self.playerState().playerID(),
                    core.build_message(
                        {core.MessageKey.trackId: self.track.id},
                        core.MessageType.atom,
                        lv2.AtomForge.build_midi_noteon(0, pitch.midi_note, 127))))

            self.__play_last_pitch = pitch

    def playNoteOff(self) -> None:
        if self.__play_last_pitch is not None:
            if self.playerState().playerID():
                self.call_async(
                    self.project_client.player_send_message(
                        self.playerState().playerID(),
                        core.build_message(
                            {core.MessageKey.trackId: self.track.id},
                            core.MessageType.atom,
                            lv2.AtomForge.build_midi_noteoff(
                                0, self.__play_last_pitch.midi_note))))

            self.__play_last_pitch = None
