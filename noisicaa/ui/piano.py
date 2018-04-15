#!/usr/bin/python

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

# mypy: loose

import math
from typing import Dict  # pylint: disable=unused-import

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPalette, QPen, QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QComboBox
)

from noisicaa import devices
from noisicaa import music
from .qled import QLed


class PianoKey(QGraphicsRectItem):
    WHITE = 0
    BLACK = 1

    def __init__(self, piano, x, name, key_type):
        super().__init__()

        self._piano = piano
        self._name = name
        self._type = key_type

        if self._type == self.WHITE:
            self.setRect(x - 10, 0, 20, 100)
            self.setBrush(QBrush(Qt.white))
            self.setPen(QPen(Qt.black))
        else:
            self.setRect(x - 7, 0, 14, 60)
            self.setBrush(QBrush(Qt.black))
            self.setPen(QPen(Qt.black))

        self.setCursor(Qt.PointingHandCursor)

    def press(self):
        self.setBrush(QBrush(QColor(0, 120, 255)))
        self._piano.noteOn.emit(
            music.Pitch(self._name), self._piano.velocity.value())

    def release(self):
        if self._type == self.WHITE:
            self.setBrush(QBrush(Qt.white))
        else:
            self.setBrush(QBrush(Qt.black))
        self._piano.noteOff.emit(music.Pitch(self._name))

    def mousePressEvent(self, event):  # pylint: disable=unused-argument
        self.press()

    def mouseReleaseEvent(self, event):  # pylint: disable=unused-argument
        self.release()


class PianoKeys(QGraphicsView):
    def __init__(self, parent):
        super().__init__(parent)

        self.setFocusPolicy(Qt.NoFocus)

        self.setBackgroundRole(QPalette.Window)
        self.setFrameShape(QFrame.NoFrame)
        self.setBackgroundBrush(QBrush(Qt.NoBrush))

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._keys = {}  # type: Dict[str, PianoKey]
        self._midi_to_key = {}  # type: Dict[int, PianoKey]
        for octave in range(2, 7):
            for idx, note in enumerate(['C', 'D', 'E', 'F', 'G', 'A', 'B']):
                pitch_name = '%s%d' % (note, octave)
                key = PianoKey(
                    parent,
                    140 * octave + 20 * idx,
                    pitch_name,
                    PianoKey.WHITE)
                self._keys[pitch_name] = key
                self._midi_to_key[music.NOTE_TO_MIDI[pitch_name]] = key
                self._scene.addItem(key)

            for idx, note in enumerate(['C#', 'D#', '', 'F#', 'G#', 'A#', '']):
                if not note:
                    continue
                pitch_name = '%s%d' % (note, octave)
                key = PianoKey(
                    parent,
                    140 * octave + 20 * idx + 10,
                    pitch_name,
                    PianoKey.BLACK)
                self._keys[pitch_name] = key
                self._midi_to_key[music.NOTE_TO_MIDI[pitch_name]] = key
                self._scene.addItem(key)


        size = self._scene.sceneRect().size()
        size = QSize(int(math.ceil(size.width())) + 1,
                     int(math.ceil(size.height())) + 10)
        self.setMinimumSize(size)
        self.setMaximumSize(size)

    _key2note = {
        0x5e: 'G2',   # <
        0x26: 'G#2',  # a
        0x34: 'A2',   # y
        0x27: 'A#2',  # s
        0x35: 'B2',   # x

        0x36: 'C3',   # c
        0x29: 'C#3',  #
        0x37: 'D3',   # v
        0x2a: 'D#3',  #
        0x38: 'E3',   # b
        0x39: 'F3',   # n
        0x2c: 'F#3',  # j
        0x3a: 'G3',   # m
        0x2d: 'G#3',  # k
        0x3b: 'A3',   # ,
        0x2e: 'A#3',  # l
        0x3c: 'B3',   # .

        0x3d: 'C4',   # -
        0x30: 'C#4',  # ä

        0x0a: 'F#4',  # 1
        0x18: 'G4',   # q
        0x0b: 'G#4',  # 2
        0x19: 'A4',   # w
        0x0c: 'A#4',  # 3
        0x1a: 'B4',   # e

        0x1b: 'C5',   # r
        0x0e: 'C#5',  # 5
        0x1c: 'D5',   # t
        0x0f: 'D#5',  # 6
        0x1d: 'E5',   # z
        0x1e: 'F5',   # u
        0x11: 'F#5',  # 8
        0x1f: 'G5',   # i
        0x12: 'G#5',  # 9
        0x20: 'A5',   # o
        0x13: 'A#5',  # 0
        0x21: 'B5',   # p

        0x22: 'C6',   # ü
        0x15: 'C#6',  # ^
        0x23: 'D6',   # ¨
    }

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            super().keyPressEvent(event)
            return

        try:
            note = self._key2note[event.nativeScanCode()]
            key = self._keys[note]
        except KeyError:
            super().keyPressEvent(event)
        else:
            key.press()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            super().keyReleaseEvent(event)
            return

        try:
            note = self._key2note[event.nativeScanCode()]
            key = self._keys[note]
        except KeyError:
            super().keyReleaseEvent(event)
        else:
            key.release()

    def midiEvent(self, event):
        if event.type in (devices.MidiEvent.NOTE_ON, devices.MidiEvent.NOTE_OFF):
            try:
                key = self._midi_to_key[event.note]
            except KeyError:
                pass
            else:
                if event.type == devices.MidiEvent.NOTE_ON:
                    key.press()
                else:
                    key.release()


class PianoWidget(QWidget):
    noteOn = pyqtSignal(music.Pitch, int)
    noteOff = pyqtSignal(music.Pitch)

    def __init__(self, parent, app):
        super().__init__(parent)

        self._app = app

        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout()
        self.setLayout(layout)

        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)

        self.focus_indicator = QLed(self)
        self.focus_indicator.setMinimumSize(24, 24)
        self.focus_indicator.setMaximumSize(24, 24)
        toolbar.addWidget(self.focus_indicator)

        toolbar.addSpacing(10)

        self._keyboard_listener = None

        self.keyboard_selector = QComboBox()
        self.keyboard_selector.addItem("None", userData=None)
        for device_id, port_info in self._app.midi_hub.list_devices():
            self.keyboard_selector.addItem(
                "%s (%s)" % (port_info.name, port_info.client_info.name),
                userData=device_id)
        self.keyboard_selector.currentIndexChanged.connect(
            self.onKeyboardDeviceChanged)
        toolbar.addWidget(self.keyboard_selector)

        toolbar.addSpacing(10)

        # speaker icon should go here...
        #tb = QToolButton(self)
        #tb.setIcon(QIcon.fromTheme('multimedia-volume-control'))
        #toolbar.addWidget(tb)

        self.velocity = QSlider(Qt.Horizontal, self)
        self.velocity.setMinimumWidth(200)
        self.velocity.setMinimum(0)
        self.velocity.setMaximum(127)
        self.velocity.setValue(127)
        self.velocity.setTickPosition(QSlider.TicksBothSides)
        toolbar.addWidget(self.velocity)

        toolbar.addStretch(1)

        self.piano_keys = PianoKeys(self)
        layout.addWidget(self.piano_keys)

    def close(self):
        if not super().close():  # pragma: no coverage
            return False

        if self._keyboard_listener is not None:
            self._keyboard_listener.remove()
            self._keyboard_listener = None

        return True

    def onKeyboardDeviceChanged(self, index):
        if self._keyboard_listener is not None:
            self._keyboard_listener.remove()
            self._keyboard_listener = None

        device_id = self.keyboard_selector.itemData(index)
        if device_id is not None:
            self._keyboard_listener = self._app.midi_hub.listeners.add(
                device_id, self.midiEvent)

    def focusInEvent(self, event):
        event.accept()
        self.focus_indicator.setValue(True)

    def focusOutEvent(self, event):
        event.accept()
        self.focus_indicator.setValue(False)

    def keyPressEvent(self, event):
        self.piano_keys.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano_keys.keyReleaseEvent(event)

    def midiEvent(self, event):
        self.piano_keys.midiEvent(event)
