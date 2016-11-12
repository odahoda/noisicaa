#!/usr/bin/python3

import logging
import enum
import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtSvg

from noisicaa import constants
from noisicaa import utils


logger = logging.getLogger(__name__)


class Tool(enum.IntEnum):
    # pylint: disable=bad-whitespace

    NOTE_WHOLE   = 100
    NOTE_HALF    = 101
    NOTE_QUARTER = 102
    NOTE_8TH     = 103
    NOTE_16TH    = 104
    NOTE_32TH    = 105

    REST_WHOLE   = 200
    REST_HALF    = 201
    REST_QUARTER = 202
    REST_8TH     = 203
    REST_16TH    = 204
    REST_32TH    = 205

    ACCIDENTAL_NATURAL      = 300
    ACCIDENTAL_FLAT         = 301
    ACCIDENTAL_SHARP        = 302
    ACCIDENTAL_DOUBLE_FLAT  = 303
    ACCIDENTAL_DOUBLE_SHARP = 304

    DURATION_DOT        = 400
    DURATION_TRIPLET    = 401
    DURATION_QUINTUPLET = 402

    POINTER = 500

    @property
    def is_note(self):
        return Tool.NOTE_WHOLE <= self <= Tool.NOTE_32TH

    @property
    def is_rest(self):
        return Tool.REST_WHOLE <= self <= Tool.REST_32TH

    @property
    def is_accidental(self):
        return Tool.ACCIDENTAL_NATURAL <= self <= Tool.ACCIDENTAL_DOUBLE_SHARP

    @property
    def is_duration(self):
        return Tool.DURATION_DOT <= self <= Tool.DURATION_QUINTUPLET

    @property
    def icon_name(self):
        return {
            Tool.POINTER: 'pointer',
            Tool.NOTE_WHOLE: 'note-whole',
            Tool.NOTE_HALF: 'note-half',
            Tool.NOTE_QUARTER: 'note-quarter',
            Tool.NOTE_8TH: 'note-8th',
            Tool.NOTE_16TH: 'note-16th',
            Tool.NOTE_32TH: 'note-32th',
            Tool.REST_WHOLE: 'rest-whole',
            Tool.REST_HALF: 'rest-half',
            Tool.REST_QUARTER: 'rest-quarter',
            Tool.REST_8TH: 'rest-8th',
            Tool.REST_16TH: 'rest-16th',
            Tool.REST_32TH: 'rest-32th',
            Tool.ACCIDENTAL_NATURAL: 'accidental-natural',
            Tool.ACCIDENTAL_SHARP: 'accidental-sharp',
            Tool.ACCIDENTAL_FLAT: 'accidental-flat',
            Tool.ACCIDENTAL_DOUBLE_SHARP: 'accidental-double-sharp',
            Tool.ACCIDENTAL_DOUBLE_FLAT: 'accidental-double-flat',
            Tool.DURATION_DOT: 'duration-dot',
            Tool.DURATION_TRIPLET: 'duration-triplet',
            Tool.DURATION_QUINTUPLET: 'duration-quintuplet',
            }[self]

    @property
    def icon_path(self):
        return os.path.join(constants.DATA_DIR, 'icons', '%s.svg' % self.icon_name)

    @utils.memoize
    def cursor(self):
        if self == Tool.POINTER:
            return QtGui.QCursor(Qt.ArrowCursor)

        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer = QtSvg.QSvgRenderer(self.icon_path)
        renderer.render(painter, QtCore.QRectF(0, 0, 64, 64))
        painter.end()

        hotspot = {
            Tool.NOTE_WHOLE:   (32, 52),
            Tool.NOTE_HALF:    (32, 52),
            Tool.NOTE_QUARTER: (32, 52),
            Tool.NOTE_8TH:     (32, 52),
            Tool.NOTE_16TH:    (32, 52),
            Tool.NOTE_32TH:    (32, 52),
            Tool.REST_WHOLE:   (32, 32),
            Tool.REST_HALF:    (32, 32),
            Tool.REST_QUARTER: (32, 32),
            Tool.REST_8TH:     (32, 32),
            Tool.REST_16TH:    (32, 32),
            Tool.REST_32TH:    (32, 32),
            Tool.ACCIDENTAL_NATURAL:      (32, 32),
            Tool.ACCIDENTAL_SHARP:        (32, 32),
            Tool.ACCIDENTAL_FLAT:         (32, 39),
            Tool.ACCIDENTAL_DOUBLE_SHARP: (32, 32),
            Tool.ACCIDENTAL_DOUBLE_FLAT:  (32, 32),
            Tool.DURATION_DOT:        (32, 52),
            Tool.DURATION_TRIPLET:    (32, 32),
            Tool.DURATION_QUINTUPLET: (32, 32),
            }[self]

        return QtGui.QCursor(pixmap, *hotspot)
