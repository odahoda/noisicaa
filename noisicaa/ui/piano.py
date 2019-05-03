#!/usr/bin/python

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

import math
from typing import Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import value_types


class PianoKey(QtWidgets.QGraphicsRectItem):
    WHITE = 0
    BLACK = 1

    def __init__(self, piano: 'PianoWidget', x: int, name: str, key_type: int) -> None:
        super().__init__()

        self._piano = piano
        self._name = name
        self._type = key_type

        if self._type == self.WHITE:
            self.setRect(x - 10, 0, 20, 100)
            self.setBrush(QtGui.QBrush(Qt.white))
            self.setPen(QtGui.QPen(Qt.black))
        else:
            self.setRect(x - 7, 0, 14, 60)
            self.setBrush(QtGui.QBrush(Qt.black))
            self.setPen(QtGui.QPen(Qt.black))

        self.setCursor(Qt.PointingHandCursor)

    def press(self) -> None:
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 255)))
        self._piano.noteOn.emit(value_types.Pitch(self._name))

    def release(self) -> None:
        if self._type == self.WHITE:
            self.setBrush(QtGui.QBrush(Qt.white))
        else:
            self.setBrush(QtGui.QBrush(Qt.black))
        self._piano.noteOff.emit(value_types.Pitch(self._name))

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        self.press()

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        self.release()


class PianoWidget(QtWidgets.QGraphicsView):
    noteOn = QtCore.pyqtSignal(value_types.Pitch)
    noteOff = QtCore.pyqtSignal(value_types.Pitch)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setBackgroundRole(QtGui.QPalette.Window)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setBackgroundBrush(QtGui.QBrush(Qt.NoBrush))

        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)

        self._keys = {}  # type: Dict[str, PianoKey]
        self._midi_to_key = {}  # type: Dict[int, PianoKey]
        for octave in range(2, 7):
            for idx, note in enumerate(['C', 'D', 'E', 'F', 'G', 'A', 'B']):
                pitch_name = '%s%d' % (note, octave)
                key = PianoKey(
                    self,
                    140 * octave + 20 * idx,
                    pitch_name,
                    PianoKey.WHITE)
                self._keys[pitch_name] = key
                self._midi_to_key[value_types.NOTE_TO_MIDI[pitch_name]] = key
                self._scene.addItem(key)

            for idx, note in enumerate(['C#', 'D#', '', 'F#', 'G#', 'A#', '']):
                if not note:
                    continue
                pitch_name = '%s%d' % (note, octave)
                key = PianoKey(
                    self,
                    140 * octave + 20 * idx + 10,
                    pitch_name,
                    PianoKey.BLACK)
                self._keys[pitch_name] = key
                self._midi_to_key[value_types.NOTE_TO_MIDI[pitch_name]] = key
                self._scene.addItem(key)


        scene_size = self._scene.sceneRect().size()
        size = QtCore.QSize(
            int(math.ceil(scene_size.width())) + 1, int(math.ceil(scene_size.height())) + 10)
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

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
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

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
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
