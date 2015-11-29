#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import math

from .qled import QLed

from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QPalette, QPen, QBrush, QColor, QCursor, QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QToolButton,
)

from noisicaa import music


class PianoKey(QGraphicsRectItem):
    WHITE = 0
    BLACK = 1

    def __init__(self, piano, x, name, type):
        super().__init__()

        self._piano = piano
        self._name = name
        self._type = type

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
            music.Pitch(self._name), self._piano.volume.value())

    def release(self):
        if self._type == self.WHITE:
            self.setBrush(QBrush(Qt.white))
        else:
            self.setBrush(QBrush(Qt.black))
        self._piano.noteOff.emit(music.Pitch(self._name))

    def mousePressEvent(self, event):
        self.press()

    def mouseReleaseEvent(self, event):
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

        self._keys = {}
        for octave in range(2, 7):
            for idx, note in enumerate(['C', 'D', 'E', 'F', 'G', 'A', 'B']):
                key = PianoKey(
                    parent,
                    140 * octave + 20 * idx,
                    '%s%d' % (note, octave),
                    PianoKey.WHITE)
                self._keys['%s%d' % (note, octave)] = key
                self._scene.addItem(key)

            for idx, note in enumerate(['C#', 'D#', '', 'F#', 'G#', 'A#', '']):
                if not note: continue
                key = PianoKey(
                    parent,
                    140 * octave + 20 * idx + 10,
                    '%s%d' % (note, octave),
                    PianoKey.BLACK)
                self._keys['%s%d' % (note, octave)] = key
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


class PianoWidget(QWidget):
    noteOn = pyqtSignal(music.Pitch, int)
    noteOff = pyqtSignal(music.Pitch)

    def __init__(self, parent):
        super().__init__(parent)

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

        # speaker icon should go here...
        #tb = QToolButton(self)
        #tb.setIcon(QIcon.fromTheme('multimedia-volume-control'))
        #toolbar.addWidget(tb)

        self.volume = QSlider(Qt.Horizontal, self)
        self.volume.setMinimumWidth(200)
        self.volume.setMinimum(0)
        self.volume.setMaximum(127)
        self.volume.setValue(127)
        self.volume.setTickPosition(QSlider.TicksBothSides)
        toolbar.addWidget(self.volume)

        toolbar.addStretch(1)

        self.piano_keys = PianoKeys(self)
        layout.addWidget(self.piano_keys)

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

