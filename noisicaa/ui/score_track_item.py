#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import music
from .instrument_library import InstrumentLibraryDialog
from .svg_symbol import SymbolItem
from .tool_dock import Tool
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item

logger = logging.getLogger(__name__)


class ScoreMeasureLayout(base_track_item.MeasureLayout):
    pass


class ScoreMeasureItemImpl(base_track_item.MeasureItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._edit_areas = []
        self._notes = []
        self._ghost = None
        self._ghost_tool = None

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

        self._layers[base_track_item.Layer.MAIN] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EDIT] = QGraphicsGroup()
        self._layers[base_track_item.Layer.EVENTS] = QGraphicsGroup()

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

    _accidental_map = {
        '': 'accidental-natural',
        '#': 'accidental-sharp',
        'b': 'accidental-flat',
        '##': 'accidental-double-sharp',
        'bb': 'accidental-double-flat',
    }

    def close(self):
        super().close()
        for listener in self._measure_listeners:
            listener.remove()
        self._measure_listeners.clear()

    def addMeasureListeners(self):
        self._measure_listeners.append(self._measure.listeners.add(
            'notes-changed', self.recomputeLayout))
        self._measure_listeners.append(self._measure.listeners.add(
            'clef', lambda *args: self.recomputeLayout()))
        self._measure_listeners.append(self._measure.listeners.add(
            'key_signature', lambda *args: self.recomputeLayout()))

    def measureChanged(self, old_value, new_value):
        super().measureChanged(old_value, new_value)

        for listener in self._measure_listeners:
            listener.remove()
        self._measure_listeners.clear()

        self.addMeasureListeners()

    def computeLayout(self):
        width = 0
        height_above = 120
        height_below = 120

        if self._measure is not None:
            width += 10

            # clef
            width += 50

            # key signature
            if self._measure.key_signature.accidentals:
                width += 10 * len(self._measure.key_signature.accidentals)
                width += 10

            # time signature
            width += 40

            width += 20

            notes_width = 0
            for note in self._measure.notes:
                notes_width += int(400 * note.duration)
            width += max(int(400 * self._measure.duration), notes_width)

            width += 10

        else:
            width += 200

        layout = ScoreMeasureLayout()
        layout.size = QtCore.QSize(width, height_above + height_below)
        layout.baseline = height_above
        return layout

    def _updateMeasureInternal(self):
        assert self._layout.width > 0 and self._layout.height > 0

        self._background.setRect(0, 0, self._layout.width, self._layout.height)

        layer = self._layers[base_track_item.Layer.MAIN]
        for child in layer.childItems():
            if child.scene() is not None:
                self.scene().removeItem(child)
            child.setParentItem(None)

        self._notes.clear()
        self._edit_areas.clear()

        is_first = (
            self._measure_reference is not None
            and self._measure_reference.index == 0)

        if self._measure is not None:
            black = Qt.black
        else:
            black = QtGui.QColor(200, 200, 200)

        if is_first and self._measure:
            track = self._measure.parent

            text = self._name_item = QtWidgets.QGraphicsSimpleTextItem(layer)
            text.setText("> %s" % track.name)
            text.setPos(0, 0)

            # TODO: update when changed
            text = self._instr_item = QtWidgets.QGraphicsSimpleTextItem(layer)
            text.setText(
                track.instrument.name if track.instrument is not None else "")
            text.setPos(0, 20)


        for l in range(-2, 3):
            line = QtWidgets.QGraphicsLineItem(layer)
            line.setLine(
                0, self._layout.baseline + 20 * l,
                self._layout.width, self._layout.baseline + 20 * l)
            line.setPen(black)

        if is_first:
            line = QtWidgets.QGraphicsRectItem(layer)
            line.setRect(0, self._layout.baseline - 40, 4, 20 * 4)
            line.setBrush(black)

        line = QtWidgets.QGraphicsLineItem(layer)
        line.setLine(
            self._layout.width, self._layout.baseline - 40,
            self._layout.width, self._layout.baseline + 40)
        line.setPen(black)

        if self._measure is not None:
            base_stave_line = self._measure.clef.center_pitch.stave_line
            base_octave = self._measure.clef.base_octave
            x = 10

            clef = SymbolItem('clef-%s' % self._measure.clef.symbol, layer)
            clef.setPos(
                x + 20,
                self._layout.baseline - 10 * (self._measure.clef.base_pitch.stave_line - base_stave_line))
            x += 50

            active_accidentals = {}
            for acc in self._measure.key_signature.accidentals:
                value = {
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
                }[acc]
                stave_line = music.Pitch(value).stave_line - base_stave_line

                sym = SymbolItem(self._accidental_map[acc[1:]], layer)
                sym.setPos(
                    x + 10,
                    self._layout.baseline - 10 * stave_line)

                active_accidentals[value[:1]] = acc[1:]
                x += 10
            if self._measure.key_signature.accidentals:
                x += 10

            font = QtGui.QFont('FreeSerif', 30, QtGui.QFont.Black)
            font.setStretch(120)

            time_sig_upper = QtWidgets.QGraphicsTextItem(layer)
            time_sig_upper.setFont(font)
            time_sig_upper.setHtml(
                '<center>%d</center>' % self._measure.time_signature.upper)
            time_sig_upper.setTextWidth(50)
            time_sig_upper.setPos(x - 10, self._layout.baseline - 52)

            time_sig_lower = QtWidgets.QGraphicsTextItem(layer)
            time_sig_lower.setFont(font)
            time_sig_lower.setHtml(
                '<center>%d</center>' % self._measure.time_signature.lower)
            time_sig_lower.setTextWidth(50)
            time_sig_lower.setPos(x - 10, self._layout.baseline - 15)
            x += 40

            px = x
            x += 20
            note_time = music.Duration(0)
            for idx, note in enumerate(self._measure.notes):
                overflow = note_time + note.duration > self._measure.duration

                if note.is_rest:
                    sym = {
                        music.Duration(1, 1): 'rest-whole',
                        music.Duration(1, 2): 'rest-half',
                        music.Duration(1, 4): 'rest-quarter',
                        music.Duration(1, 8): 'rest-8th',
                        music.Duration(1, 16): 'rest-16th',
                        music.Duration(1, 32): 'rest-32th',
                    }[note.base_duration]
                    n = SymbolItem(sym, layer)
                    n.setPos(x, self._layout.baseline)
                    self._notes.append(n)

                    if note.base_duration >= music.Duration(1, 2):
                        dx = 25
                        dy = -10
                    else:
                        dx = 12
                        dy = 0

                    for d in range(note.dots):
                        dot = QtWidgets.QGraphicsEllipseItem(n)
                        dot.setRect(dx - 4 + 10*d, dy - 4, 9, 9)
                        dot.setBrush(Qt.black)
                        dot.setPen(QtGui.QPen(Qt.NoPen))

                    if note.tuplet != 0:
                        tuplet = QtWidgets.QGraphicsSimpleTextItem(n)
                        tuplet.setText('%d' % note.tuplet)
                        tuplet.setPos(-5, -45)

                    if overflow:
                        n.setOpacity(0.4)
                elif len(note.pitches) > 0:
                    min_stave_line = 1000
                    max_stave_line = -1000

                    for pitch in note.pitches:
                        stave_line = pitch.stave_line - base_stave_line
                        min_stave_line = min(min_stave_line, stave_line)
                        max_stave_line = max(max_stave_line, stave_line)

                    # Ledger lines above stave.
                    for l in range(6, max_stave_line + 1, 2):
                        ledger = QtWidgets.QGraphicsLineItem(layer)
                        ledger.setLine(x - 20, self._layout.baseline - 10 * l,
                                       x + 20, self._layout.baseline - 10 * l)
                        ledger.setOpacity(0.8)
                        line.setPen(black)

                    # Ledger lines below stave.
                    for l in range(-6, min_stave_line - 1, -2):
                        ledger = QtWidgets.QGraphicsLineItem(layer)
                        ledger.setLine(x - 20, self._layout.baseline - 10 * l,
                                       x + 20, self._layout.baseline - 10 * l)
                        ledger.setOpacity(0.4 if overflow else 0.8)
                        line.setPen(black)

                    n = QGraphicsGroup(layer)
                    n.setPos(x, self._layout.baseline)
                    self._notes.append(n)

                    for pitch in note.pitches:
                        stave_line = pitch.stave_line - base_stave_line

                        y = -10 * stave_line

                        p = QGraphicsGroup(n)
                        p.setPos(0, y)

                        active_accidental = active_accidentals.get(pitch.value, '')
                        if pitch.accidental != active_accidental:
                            sym = self._accidental_map[pitch.accidental]
                            accidental = SymbolItem(sym, p)
                            accidental.setPos(-12, 0)
                            active_accidentals[pitch.value] = pitch.accidental

                        if note.base_duration >= music.Duration(1, 2):
                            body = SymbolItem('note-head-void', p)
                        else:
                            body = SymbolItem('note-head-black', p)

                        if note.base_duration <= music.Duration(1, 2):
                            arm = QtWidgets.QGraphicsRectItem(p)
                            arm.setRect(8, -63, 3, 60)
                            arm.setBrush(Qt.black)
                            arm.setPen(QtGui.QPen(Qt.NoPen))

                        if note.base_duration == music.Duration(1, 8):
                            flags = 1
                        elif note.base_duration == music.Duration(1, 16):
                            flags = 2
                        elif note.base_duration == music.Duration(1, 32):
                            flags = 3
                        else:
                            flags = 0
                        for f in range(flags):
                            flag = SymbolItem('note-flag-down', p)
                            flag.setPos(11, -63 + 12 * f)

                        for d in range(note.dots):
                            dot = QtWidgets.QGraphicsEllipseItem(p)
                            dot.setRect(12 + 10*d, -4, 9, 9)
                            dot.setBrush(Qt.black)
                            dot.setPen(QtGui.QPen(Qt.NoPen))

                        if note.tuplet != 0:
                            tuplet = QtWidgets.QGraphicsSimpleTextItem(p)
                            tuplet.setText('%d' % note.tuplet)
                            tuplet.setPos(-5, -85)

                    if overflow:
                        n.setOpacity(0.4)

                    if self.app.showEditAreas:
                        info = QtWidgets.QGraphicsSimpleTextItem(self)
                        info.setText(
                            '%d/%d' % (min_stave_line, max_stave_line))
                        info.setPos(x - 10, 0)

                x1 = max(x - 12, px)
                x2 = max(x + 13, x1)
                if x1 > px:
                    self._edit_areas.append((px, x1, idx, False))
                    px = x1
                if x2 > x1:
                    self._edit_areas.append((x1, x2, idx, True))
                    px = x2

                note_time += note.duration
                x += 400 * note.duration

            if px < self._layout.width:
                self._edit_areas.append(
                    (px, self._layout.width, len(self._measure.notes), False))

        if self.app.showEditAreas:
            for x1, x2, idx, overwrite in self._edit_areas:
                b = QtWidgets.QGraphicsRectItem(layer)
                b.setRect(x1, -10, x2 - x1, 5)
                b.setPen(QtGui.QPen(Qt.NoPen))
                if overwrite:
                    b.setBrush(QtGui.QColor(255, 100, 100))
                else:
                    b.setBrush(QtGui.QColor(100, 100, 255))

            if self._measure is not None:
                d = sum((n.duration for n in self._measure.notes), music.Duration(0))
                t = QtWidgets.QGraphicsSimpleTextItem(layer)
                t.setText(str(d))
                t.setPos(0, 85)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

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

        transpose_menu  = menu.addMenu("Transpose")
        transpose_menu.addAction(self._transpose_octave_up_action)
        transpose_menu.addAction(self._transpose_halfnote_up_action)
        transpose_menu.addAction(self._transpose_halfnote_down_action)
        transpose_menu.addAction(self._transpose_octave_down_action)

    def onSetClef(self, clef):
        self.send_command_async(
            self._measure.id, 'SetClef', clef=clef.value)

    def onSetKeySignature(self, key_signature):
        self.send_command_async(
            self._measure.id, 'SetKeySignature',
            key_signature=key_signature)

    def onSetTimeSignature(self, upper, lower):
        self.send_command_async(
            self._sheet_view.sheet.property_track.measure_list[self._measure_reference.index].measure.id,
            'SetTimeSignature', upper=upper, lower=lower)
        self.recomputeLayout()

    def onTranspose(self, half_notes):
        self.send_command_async(
            self._measure.track.id, 'TransposeNotes',
            note_ids=[note.id for note in self._measure.notes],
            half_notes=half_notes)

    def getEditArea(self, x):
        for x1, x2, idx, overwrite in self._edit_areas:
            if x1 < x <= x2:
                return idx, overwrite, (x1 + x2) // 2
        return -1, False, 0

    _tool_duration_map = {
        Tool.NOTE_WHOLE:   music.Duration(1, 1),
        Tool.NOTE_HALF:    music.Duration(1, 2),
        Tool.NOTE_QUARTER: music.Duration(1, 4),
        Tool.NOTE_8TH:     music.Duration(1, 8),
        Tool.NOTE_16TH:    music.Duration(1, 16),
        Tool.NOTE_32TH:    music.Duration(1, 32),

        Tool.REST_WHOLE:   music.Duration(1, 1),
        Tool.REST_HALF:    music.Duration(1, 2),
        Tool.REST_QUARTER: music.Duration(1, 4),
        Tool.REST_8TH:     music.Duration(1, 8),
        Tool.REST_16TH:    music.Duration(1, 16),
        Tool.REST_32TH:    music.Duration(1, 32),
    }

    def durationForTool(self, tool):
        assert tool.is_note or tool.is_rest
        return self._tool_duration_map[tool]

    def setGhost(self, tool):
        if tool == self._ghost_tool and self._ghost is not None:
            return
        self.removeGhost()

        layer = self._layers[base_track_item.Layer.EDIT]

        self._ghost_tool = tool
        if tool.is_note or tool.is_rest:
            self._ghost = SymbolItem('note-head-black', layer)
            self._ghost.setOpacity(0.2)
        elif tool.is_accidental:
            accidental = {
                Tool.ACCIDENTAL_NATURAL: '',
                Tool.ACCIDENTAL_FLAT: 'b',
                Tool.ACCIDENTAL_SHARP: '#',
                Tool.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                Tool.ACCIDENTAL_DOUBLE_SHARP: '##',
            }[tool]
            sym = self._accidental_map[accidental]
            self._ghost = SymbolItem(sym, layer)
            self._ghost.setOpacity(0.2)
        else:
            self._ghost = QtWidgets.QGraphicsEllipseItem(layer)
            self._ghost.setRect(-15, -15, 30, 30)
            self._ghost.setBrush(Qt.black)
            self._ghost.setPen(QtGui.QPen(Qt.NoPen))
            self._ghost.setOpacity(0.2)

    def removeGhost(self):
        if self._ghost is not None:
            self._ghost.setParentItem(None)
            if self._ghost.scene() is not None:
                self.scene().removeItem(self._ghost)
            self._ghost = None

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        self.grabMouse()

    def keyPressEvent(self, event):
        if (event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
                and event.key() == Qt.Key_Up):
            self._transpose_octave_up_action.trigger()
            event.accept()
            return

        if (event.modifiers() == Qt.ControlModifier
                and event.key() == Qt.Key_Up):
            self._transpose_halfnote_up_action.trigger()
            event.accept()
            return

        if (event.modifiers() == Qt.ControlModifier
                and event.key() == Qt.Key_Down):
            self._transpose_halfnote_down_action.trigger()
            event.accept()
            return

        if (event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
                and event.key() == Qt.Key_Down):
            self._transpose_octave_down_action.trigger()
            event.accept()
            return

        super().keyPressEvent(event)

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

        if not self._layout.is_valid:
            logger.warn("mouseMoveEvent without valid layout.")
            return

        if not self.boundingRect().contains(event.pos()):
            self._sheet_view.setInfoMessage('')
            self.removeGhost()
            self.ungrabMouse()
            return

        stave_line = int(self._layout.baseline + 5 - event.pos().y()) // 10 + self._measure.clef.center_pitch.stave_line

        idx, overwrite, insert_x = self.getEditArea(event.pos().x())
        if idx < 0:
            self._sheet_view.setInfoMessage('')
            self.removeGhost()
            return

        pitch = music.Pitch.name_from_stave_line(
            stave_line, self._measure.key_signature)
        self._sheet_view.setInfoMessage(pitch)

        tool = self._sheet_view.currentTool()
        if tool.is_note or tool.is_rest:
            self.setGhost(tool)
            self._ghost.setPos(
                insert_x,
                self._layout.baseline - 10 * (stave_line - self._measure.clef.center_pitch.stave_line))

        elif tool.is_accidental and overwrite:
            self.setGhost(tool)
            self._ghost.setPos(
                insert_x - 12,
                self._layout.baseline - 10 * (stave_line - self._measure.clef.center_pitch.stave_line))

        else:
            self.removeGhost()

    def mousePressEvent(self, event):
         # Always accept event, so we don't lose the mouse grab.
        event.accept()

        if self._measure is None:
            self.send_command_async(
                self._sheet_view.sheet.id,
                'InsertMeasure', tracks=[], pos=-1)
            return

        if not self._layout.is_valid:
            logger.warn("mousePressEvent without valid layout.")
            return

        stave_line = int(self._layout.baseline + 5 - event.pos().y()) // 10 + self._measure.clef.center_pitch.stave_line

        tool = self._sheet_view.currentTool()
        if (event.button() == Qt.LeftButton
            and (event.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
            and (tool.is_note or tool.is_rest)):
            if tool.is_note:
                pitch = music.Pitch.name_from_stave_line(
                    stave_line, self._measure.key_signature)
            else:
                pitch = 'r'

            duration = self.durationForTool(tool)

            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0:
                cmd = None
                if event.modifiers() == Qt.ShiftModifier:
                    if overwrite:
                        if len(self._measure.notes[idx].pitches) > 1:
                            for pitch_idx, p in enumerate(self._measure.notes[idx].pitches):
                                if p.stave_line == stave_line:
                                    cmd = ('RemovePitch', dict(idx=idx, pitch_idx=pitch_idx))
                                    break
                        else:
                            cmd = ('DeleteNote', dict(idx=idx))
                else:
                    if overwrite:
                        for pitch_idx, p in enumerate(self._measure.notes[idx].pitches):
                            if p.stave_line == stave_line:
                                break
                        else:
                            cmd = ('AddPitch', dict(idx=idx, pitch=pitch))
                            self._track_item.playNoteOn(music.Pitch(pitch))
                    else:
                        cmd = ('InsertNote', dict(
                            idx=idx, pitch=pitch, duration=duration))
                        self._track_item.playNoteOn(music.Pitch(pitch))

                if cmd is not None:
                    self.send_command_async(
                        self._measure.id, cmd[0], **cmd[1])
                    return

        if (event.button() == Qt.LeftButton
            and event.modifiers() == Qt.NoModifier
            and tool.is_accidental):
            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0 and overwrite:
                accidental = {
                    Tool.ACCIDENTAL_NATURAL: '',
                    Tool.ACCIDENTAL_FLAT: 'b',
                    Tool.ACCIDENTAL_SHARP: '#',
                    Tool.ACCIDENTAL_DOUBLE_FLAT: 'bb',
                    Tool.ACCIDENTAL_DOUBLE_SHARP: '##',
                }[tool]
                for pitch_idx, p in enumerate(self._measure.notes[idx].pitches):
                    if accidental in p.valid_accidentals:
                        if p.stave_line == stave_line:
                            self.send_command_async(
                                self._measure.id, 'SetAccidental',
                                idx=idx, accidental=accidental,
                                pitch_idx=pitch_idx)
                            return


        if (event.button() == Qt.LeftButton
            and (event.modifiers() & ~Qt.ShiftModifier) == Qt.NoModifier
            and tool.is_duration):
            idx, overwrite, insert_x = self.getEditArea(event.pos().x())
            if idx >= 0 and overwrite:
                note = self._measure.notes[idx]
                cmd = None
                if tool == Tool.DURATION_DOT:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.dots > 0:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots - 1))
                    else:
                        if note.dots < note.max_allowed_dots:
                            cmd = ('ChangeNote', dict(idx=idx, dots=note.dots + 1))

                elif tool == Tool.DURATION_TRIPLET:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 3:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=3))

                elif tool == Tool.DURATION_QUINTUPLET:
                    if event.modifiers() & Qt.ShiftModifier:
                        if note.tuplet != 0:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=0))
                    else:
                        if note.tuplet != 5:
                            cmd = ('ChangeNote', dict(idx=idx, tuplet=5))

                if cmd is not None:
                    self.send_command_async(
                        self._measure.id, cmd[0], **cmd[1])
                    return

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._track_item.playNoteOff()

    def clearPlaybackPos(self):
        self.playback_pos.setVisible(False)

    def setPlaybackPos(
            self, sample_pos, num_samples, start_tick, end_tick, first):
        if first:
            assert 0 <= start_tick < self._measure.duration.ticks
            assert self._layout.width > 0 and self._layout.height > 0

            pos = (
                400 * self._measure.duration
                * start_tick
                / self._measure.duration.ticks)

            # TODO: That's ugly...
            pos += 10

            # clef
            pos += 50

            # key signature
            if self._measure.key_signature.accidentals:
                pos += 10 * len(self._measure.key_signature.accidentals)
                pos += 10

            # time signature
            pos += 40

            pos += 20

            self.playback_pos.setLine(0, 0, 0, self._layout.height)
            self.playback_pos.setPos(pos, 0)
            self.playback_pos.setVisible(True)

class ScoreMeasureItem(ui_base.ProjectMixin, ScoreMeasureItemImpl):
    pass


class ScoreTrackItemImpl(base_track_item.TrackItemImpl):
    measure_item_cls = ScoreMeasureItem

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._play_last_pitch = None
        self.onInstrumentChanged(None, self._track.instrument)
        self._listeners.append(
            self._track.listeners.add('instrument', self.onInstrumentChanged))

    def onInstrumentChanged(self, old_instr, new_instr):
        logger.info("Track %s: Changed instrument from %s to %s",
                    self._track.name, old_instr, new_instr)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

        track_instrument_action = QtWidgets.QAction(
            "Select instrument...", menu,
            statusTip="Select the insturment for track.",
            triggered=self.onTrackInstrument)
        menu.addAction(track_instrument_action)

    def onTrackInstrument(self):
        if self._instrument_selector is None:
            self._instrument_selector = InstrumentLibraryDialog(
                self._sheet_view, self.app, self.app.instrument_library)
            self._instrument_selector.instrumentChanged.connect(
                self.onSelectInstrument)

        self._instrument_selector.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        self._instrument_selector.selectInstrument(self._track.instrument)
        self._instrument_selector.show()

    def onSelectInstrument(self, instr):
        if instr is not None:
            self.send_command_async(
                self._track.id, 'SetInstrument',
                instr=instr.to_json())

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


class ScoreTrackItem(ui_base.ProjectMixin, ScoreTrackItemImpl):
    pass
