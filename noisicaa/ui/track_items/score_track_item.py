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

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtSvg

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa.bindings import lv2
from noisicaa.ui import svg_symbol
from noisicaa.ui import ui_base
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class ScoreToolBase(base_track_item.MeasuredToolBase):
    def __init__(self, *, icon_name, hotspot, **kwargs):
        super().__init__(**kwargs)

        self.__icon_name = icon_name

        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer = QtSvg.QSvgRenderer(self.iconPath())
        renderer.render(painter, QtCore.QRectF(0, 0, 64, 64))
        painter.end()
        self.__cursor = QtGui.QCursor(pixmap, *hotspot)

    def iconName(self):
        return self.__icon_name

    def cursor(self):
        return self.__cursor

    def _updateGhost(self, target, pos):
        target.setGhost(None)

    def mouseMoveEvent(self, target, evt):
        assert isinstance(target, ScoreMeasureEditorItemImpl), type(target).__name__

        self._updateGhost(target, evt.pos())

        ymid = target.height() // 2
        stave_line = int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = target.getEditArea(evt.pos().x())
        if idx < 0:
            self.window.setInfoMessage('')
        else:
            pitch = music.Pitch.name_from_stave_line(
                stave_line, target.measure.key_signature)
            self.window.setInfoMessage(pitch)

        super().mouseMoveEvent(target, evt)


class InsertNoteTool(ScoreToolBase):
    def __init__(self, *, type, **kwargs):
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

    def _updateGhost(self, target, pos):
        if pos is None:
            target.setGhost(None)
            return

        ymid = target.height() // 2
        stave_line = int(ymid + 5 - pos.y()) // 10 + target.measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = target.getEditArea(pos.x())
        if idx < 0:
            target.setGhost(None)
            return

        target.setGhost(
            QtCore.QPoint(
                insert_x,
                ymid - 10 * (stave_line - target.measure.clef.center_pitch.stave_line)))

    def mousePressEvent(self, target, evt):
        ymid = target.height() // 2
        stave_line = int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line

        if (evt.button() == Qt.LeftButton
            and (evt.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier):
            if self.type.is_note:
                pitch = music.Pitch.name_from_stave_line(
                    stave_line, target.measure.key_signature)
            else:
                pitch = 'r'

            duration = target.durationForTool(self.type)

            idx, overwrite, insert_x = target.getEditArea(evt.pos().x())
            if idx >= 0:
                cmd = None
                if evt.modifiers() == Qt.ShiftModifier:
                    if overwrite:
                        if len(target.measure.notes[idx].pitches) > 1:
                            for pitch_idx, p in enumerate(target.measure.notes[idx].pitches):
                                if p.stave_line == stave_line:
                                    cmd = ('RemovePitch', dict(idx=idx, pitch_idx=pitch_idx))
                                    break
                        else:
                            cmd = ('DeleteNote', dict(idx=idx))
                else:
                    if overwrite:
                        for pitch_idx, p in enumerate(target.measure.notes[idx].pitches):
                            if p.stave_line == stave_line:
                                break
                        else:
                            cmd = ('AddPitch', dict(idx=idx, pitch=pitch))
                            target.track_item.playNoteOn(music.Pitch(pitch))
                    else:
                        cmd = ('InsertNote', dict(
                            idx=idx, pitch=pitch, duration=duration))
                        target.track_item.playNoteOn(music.Pitch(pitch))

                if cmd is not None:
                    self.send_command_async(
                        target.measure.id, cmd[0], **cmd[1])
                    evt.accept()
                    return

        return super().mousePressEvent(target, evt)

    def mouseReleaseEvent(self, target, evt):
        target.track_item.playNoteOff()
        return super().mouseReleaseEvent(target, evt)


class ModifyNoteTool(ScoreToolBase):
    def __init__(self, *, type, **kwargs):
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

    def _updateGhost(self, target, pos):
        if pos is None:
            target.setGhost(None)
            return

        ymid = target.height() // 2
        stave_line = int(ymid + 5 - pos.y()) // 10 + target.measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = target.getEditArea(pos.x())
        if idx < 0:
            target.setGhost(None)
            return

        target.setGhost(
            QtCore.QPoint(
                insert_x - 12,
                ymid - 10 * (stave_line - target.measure.clef.center_pitch.stave_line)))

    def mousePressEvent(self, target, evt):
        ymid = target.height() // 2
        stave_line = int(ymid + 5 - evt.pos().y()) // 10 + target.measure.clef.center_pitch.stave_line

        if (evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.NoModifier
            and self.type.is_accidental):
            idx, overwrite, insert_x = target.getEditArea(evt.pos().x())
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
                            self.send_command_async(
                                target.measure.id, 'SetAccidental',
                                idx=idx, accidental=accidental,
                                pitch_idx=pitch_idx)
                            evt.accept()
                            return


        if (evt.button() == Qt.LeftButton
            and (evt.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
            and self.type.is_duration):
            idx, overwrite, insert_x = target.getEditArea(evt.pos().x())
            if idx >= 0 and overwrite:
                note = target.measure.notes[idx]
                cmd = None
                if self.type == tools.ToolType.DURATION_DOT:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.dots > 0:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots - 1))
                    else:
                        if note.dots < note.max_allowed_dots:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots + 1))

                elif self.type == tools.ToolType.DURATION_TRIPLET:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 3:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=3))

                elif self.type == tools.ToolType.DURATION_QUINTUPLET:
                    if evt.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 5:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=5))

                if cmd is not None:
                    self.send_command_async(
                        target.measure.id, cmd[0], **cmd[1])
                    evt.accept()
                    return

        return super().mousePressEvent(target, evt)


class ScoreToolBox(tools.ToolBox):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.addTool(base_track_item.ArrangeMeasuresTool(**self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_WHOLE, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_HALF, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_QUARTER, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_8TH, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_16TH, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.NOTE_32TH, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_WHOLE, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_HALF, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_QUARTER, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_8TH, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_16TH, **self.context))
        self.addTool(InsertNoteTool(type=tools.ToolType.REST_32TH, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_NATURAL, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_SHARP, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_FLAT, **self.context))
        #self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_DOUBLE_SHARP, **self.context))
        #self.addTool(ModifyNoteTool(type=tools.ToolType.ACCIDENTAL_DOUBLE_FLAT, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_DOT, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_TRIPLET, **self.context))
        self.addTool(ModifyNoteTool(type=tools.ToolType.DURATION_QUINTUPLET, **self.context))

    def keyPressEvent(self, target, evt):
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

        return super().keyPressEvent(target, evt)

    def keyReleaseEvent(self, target, evt):
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

        return super().keyReleaseEvent(target, evt)

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


class ScoreMeasureEditorItemImpl(base_track_item.MeasureEditorItem):
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

        self._edit_areas = []
        self._note_area = None
        self.__mouse_pos = None
        self.__ghost_pos = None

        self.track_item.currentToolChanged.connect(
            lambda _: self.updateGhost(self.__mouse_pos))

    _accidental_map = {
        '': 'accidental-natural',
        '#': 'accidental-sharp',
        'b': 'accidental-flat',
        '##': 'accidental-double-sharp',
        'bb': 'accidental-double-flat',
    }

    def addMeasureListeners(self):
        self.measure_listeners.append(self.measure.listeners.add(
            'notes-changed',
            lambda *args: self.invalidatePaintCache(self.FOREGROUND)))
        self.measure_listeners.append(self.measure.listeners.add(
            'clef',
            lambda *args: self.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)))
        self.measure_listeners.append(self.measure.listeners.add(
            'key_signature',
            lambda *args: self.invalidatePaintCache(self.BACKGROUND, self.FOREGROUND)))

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
        painter.setBrush(Qt.black)

        for l in range(-2, 3):
            painter.drawLine(0, ymid + 20 * l, self.width() - 1, ymid + 20 * l)

        if self.is_first:
            painter.fillRect(0, ymid - 40, 2, 20 * 4, Qt.black)

        painter.drawLine(self.width() - 1, ymid - 40, self.width() - 1, ymid + 40)

        base_stave_line = self.measure.clef.center_pitch.stave_line
        base_octave = self.measure.clef.base_octave
        x = 0

        if self.width() - x > 200:
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

        active_accidentals = {}
        for acc in self.measure.key_signature.accidentals:
            value = acc_map[acc]
            active_accidentals[value[:1]] = acc[1:]

        if self.width() - x > 200:
            for acc in self.measure.key_signature.accidentals:
                value = acc_map[acc]
                stave_line = music.Pitch(value).stave_line - base_stave_line

                svg_symbol.paintSymbol(
                    painter,
                    self._accidental_map[acc[1:]],
                    QtCore.QPoint(
                        x + 10,
                        ymid - 10 * stave_line))

                x += 10

            if self.measure.key_signature.accidentals:
                x += 10

        if self.width() - x > 200:
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

    def paintForeground(self, painter):
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
            note_time = music.Duration(0)
            for idx, note in enumerate(self.measure.notes):
                overflow = note_time + note.duration > self.measure.duration

                if note.is_rest:
                    sym = {
                        music.Duration(1, 1): 'rest-whole',
                        music.Duration(1, 2): 'rest-half',
                        music.Duration(1, 4): 'rest-quarter',
                        music.Duration(1, 8): 'rest-8th',
                        music.Duration(1, 16): 'rest-16th',
                        music.Duration(1, 32): 'rest-32th',
                    }[note.base_duration]
                    svg_symbol.paintSymbol(
                        painter, sym, QtCore.QPoint(x, ymid))

                    if note.base_duration >= music.Duration(1, 2):
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

                        if note.base_duration >= music.Duration(1, 2):
                            svg_symbol.paintSymbol(
                                painter, 'note-head-void', QtCore.QPoint(x, y))
                        else:
                            svg_symbol.paintSymbol(
                                painter, 'note-head-black', QtCore.QPoint(x, y))

                        if note.base_duration <= music.Duration(1, 2):
                            painter.fillRect(x + 8, y - 63, 3, 60, Qt.black)

                        if note.base_duration == music.Duration(1, 8):
                            flags = 1
                        elif note.base_duration == music.Duration(1, 16):
                            flags = 2
                        elif note.base_duration == music.Duration(1, 32):
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
                x += int(note_area_width * note.duration)

            if px < self.width():
                self._edit_areas.append(
                    (px, self.width(), len(self.measure.notes), False))
        else:
            self._note_area = (0, self.width())

    def paintGhost(self, painter):
        if self.__ghost_pos is None:
            return

        ymid = self.height() // 2

        tool = self.track_item.currentToolType()
        pos = self.__ghost_pos
        painter.setOpacity(0.4)

        if tool.is_rest:
            sym = {
                music.Duration(1, 1): 'rest-whole',
                music.Duration(1, 2): 'rest-half',
                music.Duration(1, 4): 'rest-quarter',
                music.Duration(1, 8): 'rest-8th',
                music.Duration(1, 16): 'rest-16th',
                music.Duration(1, 32): 'rest-32th',
            }[self._tool_duration_map[tool]]
            svg_symbol.paintSymbol(
                painter, sym, QtCore.QPoint(pos.x(), ymid))

        elif tool.is_note:
            duration = self._tool_duration_map[tool]

            if duration >= music.Duration(1, 2):
                svg_symbol.paintSymbol(
                    painter, 'note-head-void', pos)
            else:
                svg_symbol.paintSymbol(
                    painter, 'note-head-black', pos)

            if duration <= music.Duration(1, 2):
                painter.fillRect(pos.x() + 8, pos.y() - 63, 3, 60, Qt.black)

            if duration == music.Duration(1, 8):
                flags = 1
            elif duration == music.Duration(1, 16):
                flags = 2
            elif duration == music.Duration(1, 32):
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

    def paintPlaybackPos(self, painter):
        assert self._note_area is not None

        left, width = self._note_area
        pos = left + int(
            width
            * self.playbackPos()
            / self.measure.duration)
        painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def getEditArea(self, x):
        for x1, x2, idx, overwrite in self._edit_areas:
            if x1 < x <= x2:
                return idx, overwrite, (x1 + x2) // 2
        return -1, False, 0

    _tool_duration_map = {
        tools.ToolType.NOTE_WHOLE:   music.Duration(1, 1),
        tools.ToolType.NOTE_HALF:    music.Duration(1, 2),
        tools.ToolType.NOTE_QUARTER: music.Duration(1, 4),
        tools.ToolType.NOTE_8TH:     music.Duration(1, 8),
        tools.ToolType.NOTE_16TH:    music.Duration(1, 16),
        tools.ToolType.NOTE_32TH:    music.Duration(1, 32),

        tools.ToolType.REST_WHOLE:   music.Duration(1, 1),
        tools.ToolType.REST_HALF:    music.Duration(1, 2),
        tools.ToolType.REST_QUARTER: music.Duration(1, 4),
        tools.ToolType.REST_8TH:     music.Duration(1, 8),
        tools.ToolType.REST_16TH:    music.Duration(1, 16),
        tools.ToolType.REST_32TH:    music.Duration(1, 32),
    }

    def durationForTool(self, tool):
        assert tool.is_note or tool.is_rest
        return self._tool_duration_map[tool]

    def setGhost(self, pos):
        if pos == self.__ghost_pos:
            return

        self.__ghost_pos = pos
        self.invalidatePaintCache(self.GHOST)

    def updateGhost(self, pos):
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

    def leaveEvent(self, evt):
        self.__mouse_pos = None
        self.setGhost(None)
        super().leaveEvent(evt)

    def mouseMoveEvent(self, evt):
        self.__mouse_pos = evt.pos()
        self.updateGhost(self.__mouse_pos)
        super().mouseMoveEvent(evt)


class ScoreMeasureEditorItem(ui_base.ProjectMixin, ScoreMeasureEditorItemImpl):
    pass


class ScoreTrackEditorItemImpl(base_track_item.MeasuredTrackEditorItem):
    measure_item_cls = ScoreMeasureEditorItem

    toolBoxClass = ScoreToolBox

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__play_last_pitch = None

        self.setHeight(240)

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        affected_measure_items = []
        if not self.selection_set.empty():
            affected_measure_items.extend(self.selection_set)
        else:
            mitem = self.measureItemAt(pos)
            if isinstance(mitem, ScoreMeasureEditorItemImpl):
                affected_measure_items.append(mitem)

        enable_measure_actions = bool(affected_measure_items)

        clef_menu = menu.addMenu("Set clef")
        for clef in music.Clef:
            clef_menu.addAction(QtWidgets.QAction(
                clef.value, menu,
                enabled=enable_measure_actions,
                triggered=lambda _, clef=clef: self.onSetClef(affected_measure_items, clef)))

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
            key_signature_menu.addAction(QtWidgets.QAction(
                key_signature, menu,
                enabled=enable_measure_actions,
                triggered=lambda _, sig=key_signature: (
                    self.onSetKeySignature(affected_measure_items, sig))))

        time_signature_menu = menu.addMenu("Set time signature")
        time_signatures = [
            (4, 4),
            (3, 4),
        ]
        for upper, lower in time_signatures:
            time_signature_menu.addAction(QtWidgets.QAction(
                "%d/%d" % (upper, lower), menu,
                enabled=enable_measure_actions,
                triggered=lambda _, upper=upper, lower=lower: (
                    self.onSetTimeSignature(affected_measure_items, upper, lower))))

        transpose_menu = menu.addMenu("Transpose")
        transpose_menu.addAction(QtWidgets.QAction(
            "Octave up", self,
            enabled=enable_measure_actions,
            shortcut='Ctrl+Shift+Up',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(affected_measure_items, 12)))
        transpose_menu.addAction(QtWidgets.QAction(
            "Half-note up", self,
            enabled=enable_measure_actions,
            shortcut='Ctrl+Up',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(affected_measure_items, 1)))
        transpose_menu.addAction(QtWidgets.QAction(
            "Half-note down", self,
            enabled=enable_measure_actions,
            shortcut='Ctrl+Down',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(affected_measure_items, -1)))
        transpose_menu.addAction(QtWidgets.QAction(
            "Octave down", self,
            enabled=enable_measure_actions,
            shortcut='Ctrl+Shift+Down',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(affected_measure_items, -12)))

    def onSetClef(self, affected_measure_items, clef):
        self.send_command_async(
            self.track.id, 'SetClef',
            measure_ids=[mitem.measure.id for mitem in affected_measure_items],
            clef=clef.value)

    def onSetKeySignature(self, affected_measure_items, key_signature):
        self.send_command_async(
            self.track.id, 'SetKeySignature',
            measure_ids=[mitem.measure.id for mitem in affected_measure_items],
            key_signature=key_signature)

    def onSetTimeSignature(self, affected_measure_items, upper, lower):
        self.send_command_async(
            self.track.id, 'SetTimeSignature',
            measure_ids=[
                self.property_track.measure_list[mitem.measure_reference.index].measure.id
                for mitem in affected_measure_items],
            upper=upper, lower=lower)

    def onTranspose(self, affected_measure_items, half_notes):
        note_ids = set()
        for mitem in affected_measure_items:
            for note in mitem.measure.notes:
                note_ids.add(note.id)

        self.send_command_async(
            self.track.id, 'TransposeNotes',
            note_ids=list(note_ids),
            half_notes=half_notes)

    def playNoteOn(self, pitch):
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

    def playNoteOff(self):
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


class ScoreTrackEditorItem(ui_base.ProjectMixin, ScoreTrackEditorItemImpl):
    pass
