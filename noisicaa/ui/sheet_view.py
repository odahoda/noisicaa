#!/usr/bin/python3

import functools
import random
import logging
import os.path
import itertools
import enum
import contextlib

from PyQt5.QtCore import Qt, QRect, QRectF, QEvent, pyqtSignal, pyqtProperty, QCoreApplication, QSize, QPoint
from PyQt5.QtGui import QIcon, QPen, QColor, QBrush, QFont
from PyQt5.QtWidgets import (
    QAction,
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsProxyWidget,
    QHBoxLayout,
    QVBoxLayout,
    QComboBox,
    QToolButton,
    QMenu,
    QMessageBox,
    QFileDialog,
    QDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QStackedWidget,
    QSpinBox,
)
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem

from noisicaa import audioproc
from .instrument_library import InstrumentLibraryDialog
from .render_sheet_dialog import RenderSheetDialog
from noisicaa.music import (
    Note,
    Duration,
    Pitch, Clef, KeySignature,
)
from ..constants import DATA_DIR
from .svg_symbol import SvgSymbol, SymbolItem
from .tool_dock import Tool
from .misc import QGraphicsGroup
from . import ui_base
from noisicaa.music import model

logger = logging.getLogger(__name__)


class MeasureLayout(object):
    def __init__(self):
        self.size = QSize()
        self.baseline = 0

    @property
    def is_valid(self):
        return self.width > 0 and self.height > 0

    @property
    def width(self):
        return self.size.width()

    @width.setter
    def width(self, value):
        self.size.setWidth(value)

    @property
    def height(self):
        return self.size.height()

    @height.setter
    def height(self, value):
        self.size.setHeight(value)

    @property
    def extend_above(self):
        return self.baseline

    @property
    def extend_below(self):
        return self.height - self.baseline

    def __eq__(self, other):
        assert isinstance(other, MeasureLayout)
        return (self.size == other.size) and (self.baseline == other.baseline)


class MeasureItemImpl(QGraphicsItem):
    def __init__(self, sheet_view, track_item, measure, **kwargs):
        super().__init__(**kwargs)
        self._sheet_view = sheet_view
        self._track_item = track_item
        self._measure = measure
        self._layout = None

        self._layers = {}

    @property
    def track_item(self):
        return self._track_item

    def boundingRect(self):
        return QRectF(0, 0, self._layout.width, self._layout.height)

    def paint(self, painter, option, widget=None):
        pass

    def close(self):
        pass

    def recomputeLayout(self):
        layout = self.computeLayout()
        if layout != self._layout:
            self._sheet_view.updateSheet()
        else:
            self.updateMeasure()

    def computeLayout(self):
        raise NotImplementedError

    def setLayout(self, layout):
        self._layout = layout

    def updateMeasure(self):
        pass

    @property
    def layers(self):
        return sorted(self._layers.keys())

    def getLayer(self, layer_id):
        return self._layers.get(layer_id, None)

    def width(self):
        return self._layout.width

    def buildContextMenu(self, menu):
        insert_measure_action = QAction(
            "Insert measure", menu,
            statusTip="Insert an empty measure at this point.",
            triggered=self.onInsertMeasure)
        menu.addAction(insert_measure_action)

        remove_measure_action = QAction(
            "Remove measure", menu,
            statusTip="Remove this measure.",
            triggered=self.onRemoveMeasure)
        menu.addAction(remove_measure_action)

    def contextMenuEvent(self, event):
        menu = QMenu()
        self._track_item.buildContextMenu(menu)
        self.buildContextMenu(menu)

        menu.exec_(event.screenPos())
        event.accept()

    def onInsertMeasure(self):
        self.send_command_async(
            self._sheet_view.sheet.id, 'InsertMeasure',
            tracks=[self._measure.track.index],
            pos=self._measure.index)

    def onRemoveMeasure(self):
        self.send_command_async(
            self._sheet_view.sheet.id, 'RemoveMeasure',
            tracks=[self._measure.track.index],
            pos=self._measure.index)


class TrackItemImpl(object):
    measure_item_cls = None

    def __init__(self, sheet_view, track, **kwargs):
        super().__init__(**kwargs)
        self._sheet_view = sheet_view
        self._track = track

        self._instrument_selector = None

        self._prev_note_highlight = None

        self._measures = []
        for measure in self._track.measures:
            measure_item = self.measure_item_cls(  # pylint: disable=not-callable
                **self.context, sheet_view=self._sheet_view,
                track_item=self, measure=measure)
            self._measures.append(measure_item)

        self._ghost_measure_item = self.measure_item_cls(  # pylint: disable=not-callable
            **self.context, sheet_view=self._sheet_view,
            track_item=self, measure=None)

        self._listeners = [
            self._track.listeners.add('name', self.onNameChanged),
            self._track.listeners.add('measures', self.onMeasuresChanged),
            self._track.listeners.add('muted', self.onMutedChanged),
            self._track.listeners.add('volume', self.onVolumeChanged),
            self._track.listeners.add('visible', self.onVisibleChanged),
        ]

    def close(self):
        for listener in self._listeners:
            listener.remove()

        while len(self._measures) > 0:
            measure = self._measures.pop(0)
            measure.close()
        self._ghost_measure_item.close()
        self._ghost_measure_item = None

    @property
    def track(self):
        return self._track

    @property
    def measures(self):
        return self._measures + [self._ghost_measure_item]

    def removeMeasure(self, idx):
        measure = self._measures[idx]
        measure.close()
        del self._measures[idx]

    def onMeasuresChanged(self, action, *args):
        if action == 'insert':
            idx, measure = args
            measure_item = self.measure_item_cls(  # pylint: disable=not-callable
                **self.context, sheet_view=self._sheet_view,
                track_item=self, measure=measure)
            self._measures.insert(idx, measure_item)
            self._sheet_view.updateSheet()

        elif action == 'delete':
            idx, measure = args
            self.removeMeasure(idx)
            self._sheet_view.updateSheet()

        else:
            raise ValueError("Unknown action %r" % action)

    def onNameChanged(self, old_name, new_name):
        # TODO: only update the first measure.
        self._sheet_view.updateSheet()

    def onMutedChanged(self, old_value, new_value):
        pass # TODO

    def onVolumeChanged(self, old_value, new_value):
        pass # TODO

    def onVisibleChanged(self, old_value, new_value):
        self._sheet_view.updateSheet()

    def buildContextMenu(self, menu):
        track_properties_action = QAction(
            "Edit track properties...", menu,
            statusTip="Edit the properties of this track.",
            triggered=self.onTrackProperties)
        menu.addAction(track_properties_action)

        remove_track_action = QAction(
            "Remove track", menu,
            statusTip="Remove this track.",
            triggered=self.onRemoveTrack)
        menu.addAction(remove_track_action)

    def onRemoveTrack(self):
        self.send_command_async(
            self._track.parent.id, 'RemoveTrack',
            track=self._track.index)

    def onTrackProperties(self):
        dialog = QDialog()
        dialog.setWindowTitle("Track Properties")

        name = QLineEdit(dialog)
        name.setText(self._track.name)

        form_layout = QFormLayout()
        form_layout.addRow("Name", name)

        close = QPushButton("Close")
        close.clicked.connect(dialog.close)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addLayout(buttons)
        dialog.setLayout(layout)

        ret = dialog.exec_()

        self.send_command_async(
            self._track.id, 'UpdateTrackProperties',
            name=name.text())


class ScoreMeasureLayout(MeasureLayout):
    pass


class ScoreMeasureItemImpl(MeasureItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._edit_areas = []
        self._notes = []
        self._ghost = None
        self._ghost_tool = None

        self._layers[Layer.BG] = QGraphicsGroup()
        self._layers[Layer.MAIN] = QGraphicsGroup()
        self._layers[Layer.EDIT] = QGraphicsGroup()

        self._background = QGraphicsRectItem(self._layers[Layer.BG])
        self._background.setPen(QPen(Qt.NoPen))
        self._background.setBrush(QColor(240, 240, 255))
        self._background.setVisible(False)

        self.setAcceptHoverEvents(True)

        if self._measure is not None:
            self._measure.listeners.add(
                'notes-changed', self.recomputeLayout)
            self._measure.listeners.add(
                'clef', lambda *args: self.recomputeLayout())
            self._measure.listeners.add(
                'key_signature', lambda *args: self.recomputeLayout())

    _accidental_map = {
        '': 'accidental-natural',
        '#': 'accidental-sharp',
        'b': 'accidental-flat',
        '##': 'accidental-double-sharp',
        'bb': 'accidental-double-flat',
    }

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
        layout.size = QSize(width, height_above + height_below)
        layout.baseline = height_above
        return layout

    def updateMeasure(self):
        assert self._layout.width > 0 and self._layout.height > 0

        self._background.setRect(0, 0, self._layout.width, self._layout.height)

        layer = self._layers[Layer.MAIN]
        for child in layer.childItems():
            if child.scene() is not None:
                self.scene().removeItem(child)
            child.setParentItem(None)

        self._notes.clear()
        self._edit_areas.clear()

        is_first = self._measure is not None and self._measure.index == 0

        if self._measure is not None:
            black = Qt.black
        else:
            black = QColor(200, 200, 200)

        if is_first and self._measure:
            track = self._measure.parent

            text = self._name_item = QGraphicsSimpleTextItem(layer)
            text.setText("> %s" % track.name)
            text.setPos(0, 0)

            # TODO: update when changed
            text = self._instr_item = QGraphicsSimpleTextItem(layer)
            text.setText(
                track.instrument.name if track.instrument is not None else "")
            text.setPos(0, 20)


        for l in range(-2, 3):
            line = QGraphicsLineItem(layer)
            line.setLine(
                0, self._layout.baseline + 20 * l,
                self._layout.width, self._layout.baseline + 20 * l)
            line.setPen(black)

        if is_first:
            line = QGraphicsRectItem(layer)
            line.setRect(0, self._layout.baseline - 40, 4, 20 * 4)
            line.setBrush(black)

        line = QGraphicsLineItem(layer)
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
                stave_line = Pitch(value).stave_line - base_stave_line

                sym = SymbolItem(self._accidental_map[acc[1:]], layer)
                sym.setPos(
                    x + 10,
                    self._layout.baseline - 10 * stave_line)

                active_accidentals[value[:1]] = acc[1:]
                x += 10
            if self._measure.key_signature.accidentals:
                x += 10

            font = QFont('FreeSerif', 30, QFont.Black)
            font.setStretch(120)

            time_sig_upper = QGraphicsTextItem(layer)
            time_sig_upper.setFont(font)
            time_sig_upper.setHtml(
                '<center>%d</center>' % self._measure.time_signature.upper)
            time_sig_upper.setTextWidth(50)
            time_sig_upper.setPos(x - 10, self._layout.baseline - 52)

            time_sig_lower = QGraphicsTextItem(layer)
            time_sig_lower.setFont(font)
            time_sig_lower.setHtml(
                '<center>%d</center>' % self._measure.time_signature.lower)
            time_sig_lower.setTextWidth(50)
            time_sig_lower.setPos(x - 10, self._layout.baseline - 15)
            x += 40

            px = x
            x += 20
            note_time = Duration(0)
            for idx, note in enumerate(self._measure.notes):
                overflow = note_time + note.duration > self._measure.duration

                if note.is_rest:
                    sym = {
                        Duration(1, 1): 'rest-whole',
                        Duration(1, 2): 'rest-half',
                        Duration(1, 4): 'rest-quarter',
                        Duration(1, 8): 'rest-8th',
                        Duration(1, 16): 'rest-16th',
                        Duration(1, 32): 'rest-32th',
                    }[note.base_duration]
                    n = SymbolItem(sym, layer)
                    n.setPos(x, self._layout.baseline)
                    self._notes.append(n)

                    if note.base_duration >= Duration(1, 2):
                        dx = 25
                        dy = -10
                    else:
                        dx = 12
                        dy = 0

                    for d in range(note.dots):
                        dot = QGraphicsEllipseItem(n)
                        dot.setRect(dx - 4 + 10*d, dy - 4, 9, 9)
                        dot.setBrush(Qt.black)
                        dot.setPen(QPen(Qt.NoPen))

                    if note.tuplet != 0:
                        tuplet = QGraphicsSimpleTextItem(n)
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
                        ledger = QGraphicsLineItem(layer)
                        ledger.setLine(x - 20, self._layout.baseline - 10 * l,
                                       x + 20, self._layout.baseline - 10 * l)
                        ledger.setOpacity(0.8)
                        line.setPen(black)

                    # Ledger lines below stave.
                    for l in range(-6, min_stave_line - 1, -2):
                        ledger = QGraphicsLineItem(layer)
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

                        if note.base_duration >= Duration(1, 2):
                            body = SymbolItem('note-head-void', p)
                        else:
                            body = SymbolItem('note-head-black', p)

                        if note.base_duration <= Duration(1, 2):
                            arm = QGraphicsRectItem(p)
                            arm.setRect(8, -63, 3, 60)
                            arm.setBrush(Qt.black)
                            arm.setPen(QPen(Qt.NoPen))

                        if note.base_duration == Duration(1, 8):
                            flags = 1
                        elif note.base_duration == Duration(1, 16):
                            flags = 2
                        elif note.base_duration == Duration(1, 32):
                            flags = 3
                        else:
                            flags = 0
                        for f in range(flags):
                            flag = SymbolItem('note-flag-down', p)
                            flag.setPos(11, -63 + 12 * f)

                        for d in range(note.dots):
                            dot = QGraphicsEllipseItem(p)
                            dot.setRect(12 + 10*d, -4, 9, 9)
                            dot.setBrush(Qt.black)
                            dot.setPen(QPen(Qt.NoPen))

                        if note.tuplet != 0:
                            tuplet = QGraphicsSimpleTextItem(p)
                            tuplet.setText('%d' % note.tuplet)
                            tuplet.setPos(-5, -85)

                    if overflow:
                        n.setOpacity(0.4)

                    if self.app.showEditAreas:
                        info = QGraphicsSimpleTextItem(self)
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
                b = QGraphicsRectItem(layer)
                b.setRect(x1, -10, x2 - x1, 5)
                b.setPen(QPen(Qt.NoPen))
                if overwrite:
                    b.setBrush(QColor(255, 100, 100))
                else:
                    b.setBrush(QColor(100, 100, 255))

            if self._measure is not None:
                d = sum((n.duration for n in self._measure.notes), Duration(0))
                t = QGraphicsSimpleTextItem(layer)
                t.setText(str(d))
                t.setPos(0, 85)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

        clef_menu = menu.addMenu("Set clef")
        for clef in Clef:
            clef_menu.addAction(QAction(
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
            key_signature_menu.addAction(QAction(
                key_signature, menu,
                triggered=lambda _, sig=key_signature: self.onSetKeySignature(sig)))

        time_signature_menu = menu.addMenu("Set time signature")
        time_signatures = [
            (4, 4),
            (3, 4),
        ]
        for upper, lower in time_signatures:
            time_signature_menu.addAction(QAction(
                "%d/%d" % (upper, lower), menu,
                triggered=lambda _, upper=upper, lower=lower: self.onSetTimeSignature(upper, lower)))

    def onSetClef(self, clef):
        self.send_command_async(
            self._measure.id, 'SetClef', clef=clef.value)

    def onSetKeySignature(self, key_signature):
        self.send_command_async(
            self._measure.id, 'SetKeySignature',
            key_signature=key_signature)

    def onSetTimeSignature(self, upper, lower):
        self.send_command_async(
            self._sheet_view.sheet.property_track.measures[self._measure.index].id,
            'SetTimeSignature', upper=upper, lower=lower)
        self.recomputeLayout()

    def getEditArea(self, x):
        for x1, x2, idx, overwrite in self._edit_areas:
            if x1 < x <= x2:
                return idx, overwrite, (x1 + x2) // 2
        return -1, False, 0

    _tool_duration_map = {
        Tool.NOTE_WHOLE:   Duration(1, 1),
        Tool.NOTE_HALF:    Duration(1, 2),
        Tool.NOTE_QUARTER: Duration(1, 4),
        Tool.NOTE_8TH:     Duration(1, 8),
        Tool.NOTE_16TH:    Duration(1, 16),
        Tool.NOTE_32TH:    Duration(1, 32),

        Tool.REST_WHOLE:   Duration(1, 1),
        Tool.REST_HALF:    Duration(1, 2),
        Tool.REST_QUARTER: Duration(1, 4),
        Tool.REST_8TH:     Duration(1, 8),
        Tool.REST_16TH:    Duration(1, 16),
        Tool.REST_32TH:    Duration(1, 32),
    }

    def durationForTool(self, tool):
        assert tool.is_note or tool.is_rest
        return self._tool_duration_map[tool]

    def setGhost(self, tool):
        if tool == self._ghost_tool and self._ghost is not None:
            return
        self.removeGhost()

        layer = self._layers[Layer.EDIT]

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
            self._ghost = QGraphicsEllipseItem(layer)
            self._ghost.setRect(-15, -15, 30, 30)
            self._ghost.setBrush(Qt.black)
            self._ghost.setPen(QPen(Qt.NoPen))
            self._ghost.setOpacity(0.2)

    def removeGhost(self):
        if self._ghost is not None:
            self._ghost.setParentItem(None)
            if self._ghost.scene() is not None:
                self.scene().removeItem(self._ghost)
            self._ghost = None

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        self._background.setVisible(True)
        self.grabMouse()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        if not self.boundingRect().contains(event.pos()):
            self._track_item.playNoteOff()
            self._sheet_view.setInfoMessage('')
            self.removeGhost()
            self.ungrabMouse()
            self._background.setVisible(False)
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

        pitch = Pitch.name_from_stave_line(
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
                pitch = Pitch.name_from_stave_line(
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
                            self._track_item.playNoteOn(Pitch(pitch))
                    else:
                        cmd = ('InsertNote', dict(
                            idx=idx, pitch=pitch, duration=duration))
                        self._track_item.playNoteOn(Pitch(pitch))

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

    def mouseReleaseEvent(self, event):
        self._track_item.playNoteOff()

class ScoreMeasureItem(ui_base.ProjectMixin, ScoreMeasureItemImpl):
    pass


class ScoreTrackItemImpl(TrackItemImpl):
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

        track_instrument_action = QAction(
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
        if instr is None:
            self.send_command_async(
                self._track.id, 'ClearInstrument')
        else:
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


class SheetPropertyMeasureLayout(MeasureLayout):
    pass


class SheetPropertyMeasureItemImpl(MeasureItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bpm_proxy = None

        self._layers[Layer.MAIN] = QGraphicsGroup()
        self._layers[Layer.EDIT] = QGraphicsGroup()

        if self._measure is not None:
            self.bpm_editor = QSpinBox(
                suffix=' bpm',
                minimum=1, maximum=1000,
                singleStep=1, accelerated=True)
            self.bpm_editor.setValue(self._measure.bpm)
            self.bpm_editor.valueChanged.connect(self.onBPMEdited)
            self.bpm_editor.editingFinished.connect(self.onBPMClose)
            self.bpm_editor.setVisible(False)

            self.bpm_proxy = QGraphicsProxyWidget(self._layers[Layer.EDIT])
            self.bpm_proxy.setWidget(self.bpm_editor)
            self.bpm_proxy.setZValue(1)

    def computeLayout(self):
        width = 100
        height_above = 10
        height_below = 10

        layout = SheetPropertyMeasureLayout()
        layout.size = QSize(width, height_above + height_below)
        layout.baseline = height_above
        return layout

    def updateMeasure(self):
        assert self._layout.width > 0 and self._layout.height > 0

        layer = self._layers[Layer.MAIN]
        self._sheet_view.clearLayer(layer)

        is_first = self._measure is not None and self._measure.index == 0

        if self._measure is not None:
            black = Qt.black
        else:
            black = QColor(200, 200, 200)

        line = QGraphicsLineItem(layer)
        line.setLine(0, self._layout.baseline,
                     self._layout.width, self._layout.baseline)
        line.setPen(black)

        if self._measure is not None:
            for i in range(self._measure.time_signature.upper):
                x = int(i * self._layout.width / self._measure.time_signature.upper)
                tick = QGraphicsLineItem(layer)
                tick.setLine(x, self._layout.baseline,
                             x, self._layout.baseline + 10)
                tick.setPen(black)

            bpm = self.bpm = QGraphicsSimpleTextItem(layer)
            bpm.setText('%d bpm' % self._measure.bpm)
            bpm.setPos(3, self._layout.baseline - bpm.boundingRect().height())
            bpm.setBrush(black)

            line = QGraphicsLineItem(layer)
            line.setLine(0, self._layout.baseline - bpm.boundingRect().height(),
                         0, self._layout.baseline)
            line.setPen(black)

            self.bpm_proxy.setPos(
                3, self._layout.baseline - bpm.boundingRect().height())

    def mousePressEvent(self, event):
        if self._measure is None:
            self.send_command_async(
                self._sheet_view.sheet.id,
                'InsertMeasure', tracks=[], pos=-1)
            event.accept()
            return

        if self._layout.width <= 0 or self._layout.height <= 0:
            logger.warn("mousePressEvent without valid layout.")
            return

        self.bpm_editor.setVisible(True)
        self.bpm_editor.selectAll()
        self.bpm_editor.setFocus()

        return super().mousePressEvent(event)

    def buildContextMenu(self, menu):
        super().buildContextMenu(menu)

    def onBPMEdited(self, value):
        self.send_command_async(
            self._measure.id, 'SetBPM', bpm=value)
        self.bpm.setText('%d bpm' % value)

    def onBPMClose(self):
        self.bpm_editor.setVisible(False)


class SheetPropertyMeasureItem(
        ui_base.ProjectMixin, SheetPropertyMeasureItemImpl):
    pass


class SheetPropertyTrackItemImpl(TrackItemImpl):
    measure_item_cls = SheetPropertyMeasureItem


class SheetPropertyTrackItem(
        ui_base.ProjectMixin, SheetPropertyTrackItemImpl):
    pass


class TrackGroupMeasureLayout(MeasureLayout):
    pass


class TrackGroupMeasureItemImpl(MeasureItemImpl):
    def computeLayout(self):
        width = 100
        height_above = 10
        height_below = 10

        layout = TrackGroupMeasureLayout()
        layout.size = QSize(width, height_above + height_below)
        layout.baseline = height_above
        return layout


class TrackGroupMeasureItem(
        ui_base.ProjectMixin, TrackGroupMeasureItemImpl):
    pass


class TrackGroupItemImpl(TrackItemImpl):
    measure_item_cls = TrackGroupMeasureItem


class TrackGroupItem(
        ui_base.ProjectMixin, TrackGroupItemImpl):
    pass


class SheetScene(QGraphicsScene):
    mouseHovers = pyqtSignal(bool)

    def event(self, event):
        if event.type() == QEvent.Enter:
            self.mouseHovers.emit(True)
        elif event.type() == QEvent.Leave:
            self.mouseHovers.emit(False)
        return super().event(event)


class Layer(enum.IntEnum):
    BG = 0
    MAIN = 1
    DEBUG = 2
    EDIT = 3
    MOUSE = 4
    EVENTS = 5

    NUM_LAYERS = 6


class SheetViewImpl(QGraphicsView):
    currentToolChanged = pyqtSignal(Tool)

    track_cls_map = {
        'ScoreTrack': ScoreTrackItem,
        'SheetPropertyTrack': SheetPropertyTrackItem,
        'TrackGroup': TrackGroupItem,
    }

    def __init__(self, sheet, **kwargs):
        super().__init__(**kwargs)
        self._sheet = sheet

        self._track_items = {}
        self._group_listeners = {}
        for track in self._sheet.master_group.walk_tracks(
                groups=True, tracks=True):
            self.addTrack(track)

        self._property_track_item = self.createTrackItem(
            self._sheet.property_track)

        self._layouts = []

        self._scene = SheetScene()
        self._scene.mouseHovers.connect(self.onMouseHovers)
        self.setScene(self._scene)

        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        #self.setDragMode(QGraphicsView.ScrollHandDrag)

        self._layers = {}
        for layer_id in range(Layer.NUM_LAYERS):
            layer = QGraphicsGroup()
            layer.setPos(0, 0)
            self._layers[layer_id] = layer
            self._scene.addItem(layer)

        self._current_tool = Tool.NOTE_QUARTER
        self._previous_tool = -1
        self._cursor = QGraphicsGroup(self._layers[Layer.MOUSE])

        self.updateSheet()

        self._player_id = None
        self._player_stream_address = None
        self._player_node_id = None

    async def setup(self):
        self._player_id, self._player_stream_address = await self.project_client.create_player(self._sheet.id)
        self._player_node_id = await self.audioproc_client.add_node(
            'ipc',
            address=self._player_stream_address,
            event_queue_name='sheet:%s' % self._sheet.id)
        await self.audioproc_client.connect_ports(
            self._player_node_id, 'out', 'sink', 'in')

    async def cleanup(self):
        while len(self._track_items) > 0:
            self.removeTrack(next(self._track_items.values()))

        if self._player_node_id is not None:
            await self.audioproc_client.disconnect_ports(
                self._player_node_id, 'out', 'sink', 'in')
            await self.audioproc_client.remove_node(
                self._player_node_id)
            self._player_node_id = None
            self._player_stream_address = None

        if self._player_id is not None:
            await self.project_client.delete_player(self._player_id)
            self._player_id = None

    @property
    def trackItems(self):
        return [
            self._track_items[track.id]
            for track in self._sheet.master_group.walk_tracks()]

    def setInfoMessage(self, msg):
        self.window.setInfoMessage(msg)

    def createTrackItem(self, track):
        track_item_cls = self.track_cls_map[type(track).__name__]
        return track_item_cls(
            **self.context, sheet_view=self, track=track)

    def addTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = track.listeners.add(
                'tracks',
                functools.partial(self.onTracksChanged, track))
            self._group_listeners[track.id] = listener
        else:
            track_item = self.createTrackItem(track)
            self._track_items[track.id] = track_item

    def removeTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = self._group_listeners[track.id]
            listener.remove()
            del self._group_listeners[track.id]
        else:
            track_item = self._track_items[track.id]
            track_item.close()
            del self._track_items[track.id]

    @property
    def sheet(self):
        return self._sheet

    def currentTool(self):
        return self._current_tool

    def setCurrentTool(self, tool_id):
        if tool_id == self._current_tool:
            return

        tool = Tool(tool_id)
        assert tool_id >= 0

        self._previous_tool = self._current_tool
        self._current_tool = tool

        for child in self._cursor.childItems():
            child.setParentItem(None)
            if child.scene() is not None:
                self._scene.removeItem(child)

        if tool_id.is_note:
            cursor = QGraphicsGroup(self._cursor)

            if tool_id <= Tool.NOTE_HALF:
                body = SymbolItem('note-head-void', cursor)
            else:
                body = SymbolItem('note-head-black', cursor)

            if tool_id >= Tool.NOTE_HALF:
                arm = QGraphicsRectItem(cursor)
                arm.setRect(8, -63, 3, 60)
                arm.setBrush(Qt.black)
                arm.setPen(QPen(Qt.NoPen))

            if tool_id >= Tool.NOTE_8TH:
                for n in range(tool_id - Tool.NOTE_QUARTER):
                    flag = SymbolItem('note-flag-down', cursor)
                    flag.setPos(11, -63 + 12 * n)

            cursor.setScale(0.8)

        elif tool_id.is_rest:
            sym = {
                Tool.REST_WHOLE: 'rest-whole',
                Tool.REST_HALF: 'rest-half',
                Tool.REST_QUARTER: 'rest-quarter',
                Tool.REST_8TH: 'rest-8th',
                Tool.REST_16TH: 'rest-16th',
                Tool.REST_32TH: 'rest-32th',
            }[tool_id]
            cursor = SymbolItem(sym, self._cursor)
            cursor.setScale(0.8)

        elif tool_id.is_accidental:
            sym = {
                Tool.ACCIDENTAL_NATURAL: 'accidental-natural',
                Tool.ACCIDENTAL_SHARP: 'accidental-sharp',
                Tool.ACCIDENTAL_FLAT: 'accidental-flat',
                Tool.ACCIDENTAL_DOUBLE_SHARP: 'accidental-double-sharp',
                Tool.ACCIDENTAL_DOUBLE_FLAT: 'accidental-double-flat',
            }[tool_id]
            cursor = SymbolItem(sym, self._cursor)
            cursor.setScale(0.8)

        elif tool_id.is_duration:
            if tool_id == Tool.DURATION_DOT:
                body = SymbolItem('note-head-black', self._cursor)
                arm = QGraphicsRectItem(self._cursor)
                arm.setRect(8, -63, 3, 60)
                arm.setBrush(Qt.black)
                arm.setPen(QPen(Qt.NoPen))
                dot = QGraphicsEllipseItem(self._cursor)
                dot.setRect(12, -4, 9, 9)
                dot.setBrush(Qt.black)
                dot.setPen(QPen(Qt.NoPen))

            else:
                sym = {
                    Tool.DURATION_TRIPLET: 'duration-triplet',
                    Tool.DURATION_QUINTUPLET: 'duration-quintuplet',
                }[tool_id]
                SymbolItem(sym, self._cursor)

        else:  # pragma: no cover
            a = QGraphicsEllipseItem(self._cursor)
            a.setRect(-5, -5, 11, 11)
            a.setPen(QPen(Qt.white))
            a.setBrush(QColor(100, 100, 100))
            a = QGraphicsSimpleTextItem(self._cursor)
            a.setText(str(tool_id))
            a.setPos(10, 10)

        self.currentToolChanged.emit(self._current_tool)

    def updateView(self):
        self.updateSheet()

    def clearLayer(self, layer):
        for item in layer.childItems():
            if item.scene() is not None:
                self._scene.removeItem(item)
            item.setParentItem(None)

    def computeLayout(self):
        track_items = [self._property_track_item] + self.trackItems

        self._layouts = []
        for track_item in track_items:
            track_layouts = []
            self._layouts.append(track_layouts)

            height_above = 0
            height_below = 0
            for measure_item in track_item.measures:
                layout = measure_item.computeLayout()
                track_layouts.append(layout)
                height_above = max(height_above, layout.extend_above)
                height_below = max(height_below, layout.extend_below)

            for layout in track_layouts:
                layout.size = QSize(layout.width, height_above + height_below)
                layout.baseline = height_above

        for column_layouts in itertools.zip_longest(*self._layouts):
            width = 0
            for layout in filter(lambda l: l is not None, column_layouts):
                width = max(width, layout.width)
            for layout in filter(lambda l: l is not None, column_layouts):
                layout.width = width

        for track_item, track_layouts in zip(track_items, self._layouts):
            for measure_item, layout in zip(track_item.measures, track_layouts):
                measure_item.setLayout(layout)

    def updateSheet(self):
        for layer_id in (Layer.BG, Layer.MAIN, Layer.DEBUG, Layer.EVENTS):
            self.clearLayer(self._layers[layer_id])

        text = QGraphicsSimpleTextItem(self._layers[Layer.MAIN])
        text.setText(
            "%s/%s" % (self.project_connection.name, self._sheet.name))
        text.setPos(0, 0)

        track_items = [self._property_track_item] + self.trackItems

        self.computeLayout()

        max_x = 200

        y = 30
        for track_item, track_layouts in zip(track_items, self._layouts):
            if not track_item.track.visible:
                continue

            x = 10
            track_height = 20
            for measure, layout in zip(track_item.measures, track_layouts):
                measure.updateMeasure()
                for mlayer_id in measure.layers:
                    slayer = self._layers[mlayer_id]
                    mlayer = measure.getLayer(mlayer_id)
                    assert mlayer is not None
                    mlayer.setParentItem(slayer)
                    mlayer.setPos(x, y)
                measure.setParentItem(self._layers[Layer.EVENTS])
                measure.setPos(x, y)

                track_height = max(track_height, layout.height)
                max_x = max(max_x, x + layout.width)
                x += layout.width

            y += track_height + 20

        if self.app.showEditAreas:  # pragma: no cover
            bbox = QGraphicsRectItem(self._layers[Layer.DEBUG])
            bbox.setRect(0, 0, max_x, y)
            bbox.setPen(QColor(200, 200, 200))
            bbox.setBrush(QBrush(Qt.NoBrush))

        self.setSceneRect(-10, -10, max_x + 20, y + 20)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        scenePos = self.mapToScene(event.pos())
        self._cursor.setPos(scenePos)

    def onMouseHovers(self, hovers):
        if hovers:
            self.setCursor(Qt.BlankCursor)
            self._cursor.show()
        else:
            self.unsetCursor()
            self._cursor.hide()

        if hovers:
            self.setFocus()

    def onTracksChanged(self, group, action, *args):
        if action == 'insert':
            idx, track = args
            self.addTrack(track)
            self.updateSheet()

        elif action == 'delete':
            idx, track = args
            self.removeTrack(track)
            self.updateSheet()

        else:  # pragma: no cover
            raise ValueError("Unknown action %r" % action)

    def onAddTrack(self, track_type):
        self.send_command_async(
            self._sheet.id, 'AddTrack', track_type=track_type)

    def onPlayerStart(self):
        if self._player_id is None:
            logger.warning("Player start action without active player.")
            return

        self.call_async(
            self.project_client.player_start(self._player_id))

    def onPlayerPause(self):
        if self._player_id is None:
            logger.warning("Player pause action without active player.")
            return

        self.call_async(
            self.project_client.player_pause(self._player_id))

    def onPlayerStop(self):
        if self._player_id is None:
            logger.warning("Player stop action without active player.")
            return

        self.call_async(
            self.project_client.player_stop(self._player_id))

    def onRender(self):
        dialog = RenderSheetDialog(self, self.app, self._sheet)
        dialog.exec_()

    def scrollToPlaybackPosition(self, pos):
        # I would rather like to keep the pos in the left 1/3rd of the view.
        # But haven't figured out how to do that...
        self.ensureVisible(
            pos.x(), self.mapToScene(0, self.size().height() / 2).y(),
            1, 1,
            self.size().width() / 3, 0)

    def keyPressEvent(self, event):
        try:
            if event.isAutoRepeat():
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_Period:
                self.setCurrentTool(Tool.DURATION_DOT)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_F:
                self.setCurrentTool(Tool.ACCIDENTAL_FLAT)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_S:
                self.setCurrentTool(Tool.ACCIDENTAL_SHARP)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_N:
                self.setCurrentTool(Tool.ACCIDENTAL_NATURAL)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_R:
                self.setCurrentTool({
                    Tool.NOTE_WHOLE: Tool.REST_WHOLE,
                    Tool.NOTE_HALF: Tool.REST_HALF,
                    Tool.NOTE_QUARTER: Tool.REST_QUARTER,
                    Tool.NOTE_8TH: Tool.REST_8TH,
                    Tool.NOTE_16TH: Tool.REST_16TH,
                    Tool.NOTE_32TH: Tool.REST_32TH,
                    Tool.REST_WHOLE: Tool.NOTE_WHOLE,
                    Tool.REST_HALF: Tool.NOTE_HALF,
                    Tool.REST_QUARTER: Tool.NOTE_QUARTER,
                    Tool.REST_8TH: Tool.NOTE_8TH,
                    Tool.REST_16TH: Tool.NOTE_16TH,
                    Tool.REST_32TH: Tool.NOTE_32TH,
                }.get(self.currentTool(), Tool.REST_QUARTER))
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_1:
                self.setCurrentTool(Tool.NOTE_WHOLE if not self.currentTool().is_rest else Tool.REST_WHOLE)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_2:
                self.setCurrentTool(Tool.NOTE_HALF if not self.currentTool().is_rest else Tool.REST_HALF)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_3:
                self.setCurrentTool(Tool.NOTE_QUARTER if not self.currentTool().is_rest else Tool.REST_QUARTER)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_4:
                self.setCurrentTool(Tool.NOTE_8TH if not self.currentTool().is_rest else Tool.REST_8TH)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_5:
                self.setCurrentTool(Tool.NOTE_16TH if not self.currentTool().is_rest else Tool.REST_16TH)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_6:
                self.setCurrentTool(Tool.NOTE_32TH if not self.currentTool().is_rest else Tool.REST_32TH)

                event.accept()
                return

        finally:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        try:
            if event.isAutoRepeat():
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_Period:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_F:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_S:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_N:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

        finally:
            super().keyReleaseEvent(event)


class SheetView(ui_base.ProjectMixin, SheetViewImpl):
    pass
