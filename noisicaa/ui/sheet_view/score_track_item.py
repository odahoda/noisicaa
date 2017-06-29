#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa.bindings import lv2
from noisicaa.ui import svg_symbol
from noisicaa.ui import ui_base
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


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

        self._transpose_octave_up_action = QtWidgets.QAction(
            "Octave up", self,
            shortcut='Ctrl+Shift+Up',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(12))
        self._transpose_halfnote_up_action = QtWidgets.QAction(
            "Half-note up", self,
            shortcut='Ctrl+Up',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(1))
        self._transpose_halfnote_down_action = QtWidgets.QAction(
            "Half-note down", self,
            shortcut='Ctrl+Down',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(-1))
        self._transpose_octave_down_action = QtWidgets.QAction(
            "Octave down", self,
            shortcut='Ctrl+Shift+Down',
            shortcutContext=Qt.WidgetWithChildrenShortcut,
            triggered=lambda _: self.onTranspose(-12))

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

        tool = self.track_item.currentTool()
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
                tools.Tool.ACCIDENTAL_NATURAL: '',
                tools.Tool.ACCIDENTAL_FLAT: 'b',
                tools.Tool.ACCIDENTAL_SHARP: '#',
                tools.Tool.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                tools.Tool.ACCIDENTAL_DOUBLE_SHARP: '##',
            }[tool]
            sym = self._accidental_map[accidental]
            svg_symbol.paintSymbol(painter, sym, pos)

        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.black)
            painter.drawEllipse(pos.x() - 15, pos.y() - 15, 31, 31, Qt.black)

    def paintPlaybackPos(self, painter):
        assert self._note_area is not None

        left, width = self._note_area
        pos = left + int(
            width
            * self.playbackPos()
            / self.measure.duration)
        painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        clef_menu = menu.addMenu("Set clef")
        for clef in music.Clef:
            clef_menu.addAction(QtWidgets.QAction(
                clef.value, menu,
                triggered=lambda _, clef=clef: self.onSetClef(clef)))

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
                triggered=lambda _, sig=key_signature: self.onSetKeySignature(sig)))

        time_signature_menu = menu.addMenu("Set time signature")
        time_signatures = [
            (4, 4),
            (3, 4),
        ]
        for upper, lower in time_signatures:
            time_signature_menu.addAction(QtWidgets.QAction(
                "%d/%d" % (upper, lower), menu,
                triggered=lambda _, upper=upper, lower=lower: self.onSetTimeSignature(upper, lower)))

        transpose_menu = menu.addMenu("Transpose")
        transpose_menu.addAction(self._transpose_octave_up_action)
        transpose_menu.addAction(self._transpose_halfnote_up_action)
        transpose_menu.addAction(self._transpose_halfnote_down_action)
        transpose_menu.addAction(self._transpose_octave_down_action)

    def onSetClef(self, clef):
        self.send_command_async(
            self.measure.id, 'SetClef', clef=clef.value)

    def onSetKeySignature(self, key_signature):
        self.send_command_async(
            self.measure.id, 'SetKeySignature',
            key_signature=key_signature)

    def onSetTimeSignature(self, upper, lower):
        self.send_command_async(
            self.property_track.measure_list[self.measure_reference.index].measure.id,
            'SetTimeSignature', upper=upper, lower=lower)
        self.recomputeLayout()

    def onTranspose(self, half_notes):
        self.send_command_async(
            self.track.id, 'TransposeNotes',
            note_ids=[note.id for note in self.measure.notes],
            half_notes=half_notes)

    def getEditArea(self, x):
        for x1, x2, idx, overwrite in self._edit_areas:
            if x1 < x <= x2:
                return idx, overwrite, (x1 + x2) // 2
        return -1, False, 0

    _tool_duration_map = {
        tools.Tool.NOTE_WHOLE:   music.Duration(1, 1),
        tools.Tool.NOTE_HALF:    music.Duration(1, 2),
        tools.Tool.NOTE_QUARTER: music.Duration(1, 4),
        tools.Tool.NOTE_8TH:     music.Duration(1, 8),
        tools.Tool.NOTE_16TH:    music.Duration(1, 16),
        tools.Tool.NOTE_32TH:    music.Duration(1, 32),

        tools.Tool.REST_WHOLE:   music.Duration(1, 1),
        tools.Tool.REST_HALF:    music.Duration(1, 2),
        tools.Tool.REST_QUARTER: music.Duration(1, 4),
        tools.Tool.REST_8TH:     music.Duration(1, 8),
        tools.Tool.REST_16TH:    music.Duration(1, 16),
        tools.Tool.REST_32TH:    music.Duration(1, 32),
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

        tool = self.track_item.currentTool()
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

    def keyPressEvent(self, evt):
        if (evt.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
                and evt.key() == Qt.Key_Up):
            self._transpose_octave_up_action.trigger()
            evt.accept()
            return

        if (evt.modifiers() == Qt.ControlModifier
                and evt.key() == Qt.Key_Up):
            self._transpose_halfnote_up_action.trigger()
            evt.accept()
            return

        if (evt.modifiers() == Qt.ControlModifier
                and evt.key() == Qt.Key_Down):
            self._transpose_halfnote_down_action.trigger()
            evt.accept()
            return

        if (evt.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
                and evt.key() == Qt.Key_Down):
            self._transpose_octave_down_action.trigger()
            evt.accept()
            return

        super().keyPressEvent(evt)

    def mouseMoveEvent(self, evt):
        self.__mouse_pos = evt.pos()

        self.updateGhost(evt.pos())

        ymid = self.height() // 2
        stave_line = int(ymid + 5 - evt.pos().y()) // 10 + self.measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = self.getEditArea(evt.pos().x())
        if idx < 0:
            self.window.setInfoMessage('')
        else:
            pitch = music.Pitch.name_from_stave_line(
                stave_line, self.measure.key_signature)
            self.window.setInfoMessage(pitch)

        super().mouseMoveEvent(evt)

    def mousePressEvent(self, event):
        ymid = self.height() // 2
        stave_line = int(ymid + 5 - event.pos().y()) // 10 + self.measure.clef.center_pitch.stave_line

        tool = self.track_item.currentTool()
        if (event.button() == Qt.LeftButton
            and (event.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
            and (tool.is_note or tool.is_rest)):
            if tool.is_note:
                pitch = music.Pitch.name_from_stave_line(
                    stave_line, self.measure.key_signature)
            else:
                pitch = 'r'

            duration = self.durationForTool(tool)

            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0:
                cmd = None
                if event.modifiers() == Qt.ShiftModifier:
                    if overwrite:
                        if len(self.measure.notes[idx].pitches) > 1:
                            for pitch_idx, p in enumerate(self.measure.notes[idx].pitches):
                                if p.stave_line == stave_line:
                                    cmd = ('RemovePitch', dict(idx=idx, pitch_idx=pitch_idx))
                                    break
                        else:
                            cmd = ('DeleteNote', dict(idx=idx))
                else:
                    if overwrite:
                        for pitch_idx, p in enumerate(self.measure.notes[idx].pitches):
                            if p.stave_line == stave_line:
                                break
                        else:
                            cmd = ('AddPitch', dict(idx=idx, pitch=pitch))
                            self.track_item.playNoteOn(music.Pitch(pitch))
                    else:
                        cmd = ('InsertNote', dict(
                            idx=idx, pitch=pitch, duration=duration))
                        self.track_item.playNoteOn(music.Pitch(pitch))

                if cmd is not None:
                    self.send_command_async(
                        self.measure.id, cmd[0], **cmd[1])
                    event.accept()
                    return

        if (event.button() == Qt.LeftButton
            and event.modifiers() == Qt.NoModifier
            and tool.is_accidental):
            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0 and overwrite:
                accidental = {
                    tools.Tool.ACCIDENTAL_NATURAL: '',
                    tools.Tool.ACCIDENTAL_FLAT: 'b',
                    tools.Tool.ACCIDENTAL_SHARP: '#',
                    tools.Tool.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                    tools.Tool.ACCIDENTAL_DOUBLE_SHARP: '##',
                }[tool]
                for pitch_idx, p in enumerate(self.measure.notes[idx].pitches):
                    if accidental in p.valid_accidentals:
                        if p.stave_line == stave_line:
                            self.send_command_async(
                                self.measure.id, 'SetAccidental',
                                idx=idx, accidental=accidental,
                                pitch_idx=pitch_idx)
                            event.accept()
                            return


        if (event.button() == Qt.LeftButton
            and (event.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
            and tool.is_duration):
            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0 and overwrite:
                note = self.measure.notes[idx]
                cmd = None
                if tool == tools.Tool.DURATION_DOT:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.dots > 0:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots - 1))
                    else:
                        if note.dots < note.max_allowed_dots:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots + 1))

                elif tool == tools.Tool.DURATION_TRIPLET:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 3:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=3))

                elif tool == tools.Tool.DURATION_QUINTUPLET:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 5:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=5))

                if cmd is not None:
                    self.send_command_async(
                        self.measure.id, cmd[0], **cmd[1])
                    event.accept()
                    return

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        logger.info(str(event))
        self.track_item.playNoteOff()


class ScoreMeasureEditorItem(ui_base.ProjectMixin, ScoreMeasureEditorItemImpl):
    pass


class ScoreTrackEditorItemImpl(base_track_item.MeasuredTrackEditorItem):
    measure_item_cls = ScoreMeasureEditorItem

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__play_last_pitch = None

        self.setHeight(240)

    def supportedTools(self):
        return {
            tools.Tool.NOTE_WHOLE,
            tools.Tool.NOTE_HALF,
            tools.Tool.NOTE_QUARTER,
            tools.Tool.NOTE_8TH,
            tools.Tool.NOTE_16TH,
            tools.Tool.NOTE_32TH,
            tools.Tool.REST_WHOLE,
            tools.Tool.REST_HALF,
            tools.Tool.REST_QUARTER,
            tools.Tool.REST_8TH,
            tools.Tool.REST_16TH,
            tools.Tool.REST_32TH,
            tools.Tool.ACCIDENTAL_NATURAL,
            tools.Tool.ACCIDENTAL_FLAT,
            tools.Tool.ACCIDENTAL_SHARP,
            tools.Tool.ACCIDENTAL_DOUBLE_FLAT,
            tools.Tool.ACCIDENTAL_DOUBLE_SHARP,
            tools.Tool.DURATION_DOT,
            tools.Tool.DURATION_TRIPLET,
            tools.Tool.DURATION_QUINTUPLET,
            }

    def defaultTool(self):
        return tools.Tool.NOTE_QUARTER

    def playNoteOn(self, pitch):
        self.playNoteOff()

        if self.playerState().playerID():
            self.call_async(
                self.project_client.player_send_message(
                    self.playerState().playerID(),
                    core.build_message(
                        {core.MessageKey.sheetId: self.sheet.id,
                         core.MessageKey.trackId: self.track.id},
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
                            {core.MessageKey.sheetId: self.sheet.id,
                             core.MessageKey.trackId: self.track.id},
                            core.MessageType.atom,
                            lv2.AtomForge.build_midi_noteoff(
                                0, self.__play_last_pitch.midi_note))))

            self.__play_last_pitch = None

    def keyPressEvent(self, evt):
        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_Period):
            self.setCurrentTool(tools.Tool.DURATION_DOT)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_F):
            self.setCurrentTool(tools.Tool.ACCIDENTAL_FLAT)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_S):
            self.setCurrentTool(tools.Tool.ACCIDENTAL_SHARP)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_N):
            self.setCurrentTool(tools.Tool.ACCIDENTAL_NATURAL)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_R):
            self.setCurrentTool({
                tools.Tool.NOTE_WHOLE: tools.Tool.REST_WHOLE,
                tools.Tool.NOTE_HALF: tools.Tool.REST_HALF,
                tools.Tool.NOTE_QUARTER: tools.Tool.REST_QUARTER,
                tools.Tool.NOTE_8TH: tools.Tool.REST_8TH,
                tools.Tool.NOTE_16TH: tools.Tool.REST_16TH,
                tools.Tool.NOTE_32TH: tools.Tool.REST_32TH,
                tools.Tool.REST_WHOLE: tools.Tool.NOTE_WHOLE,
                tools.Tool.REST_HALF: tools.Tool.NOTE_HALF,
                tools.Tool.REST_QUARTER: tools.Tool.NOTE_QUARTER,
                tools.Tool.REST_8TH: tools.Tool.NOTE_8TH,
                tools.Tool.REST_16TH: tools.Tool.NOTE_16TH,
                tools.Tool.REST_32TH: tools.Tool.NOTE_32TH,
            }.get(self.currentTool(), tools.Tool.REST_QUARTER))
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_1):
            self.setCurrentTool(
                tools.Tool.NOTE_WHOLE
                if not self.currentTool().is_rest
                else tools.Tool.REST_WHOLE)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_2):
            self.setCurrentTool(
                tools.Tool.NOTE_HALF
                if not self.currentTool().is_rest
                else tools.Tool.REST_HALF)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_3):
            self.setCurrentTool(
                tools.Tool.NOTE_QUARTER
                if not self.currentTool().is_rest
                else tools.Tool.REST_QUARTER)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_4):
            self.setCurrentTool(
                tools.Tool.NOTE_8TH if
                not self.currentTool().is_rest
                else tools.Tool.REST_8TH)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_5):
            self.setCurrentTool(
                tools.Tool.NOTE_16TH
                if not self.currentTool().is_rest
                else tools.Tool.REST_16TH)
            evt.accept()
            return

        if (not evt.isAutoRepeat()
                and evt.modifiers() == Qt.NoModifier
                and evt.key() == Qt.Key_6):
            self.setCurrentTool(
                tools.Tool.NOTE_32TH
                if not self.currentTool().is_rest
                else tools.Tool.REST_32TH)

            evt.accept()
            return

        return super().keyPressEvent(evt)

    def keyReleaseEvent(self, evt):
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

        return super().keyReleaseEvent(evt)


class ScoreTrackEditorItem(ui_base.ProjectMixin, ScoreTrackEditorItemImpl):
    pass
