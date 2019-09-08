#/usr/bin/python3

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

from typing import List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisidev import uitest
from noisicaa import audioproc
from noisicaa import value_types
from . import pianoroll


MEVT = value_types.MidiEvent
MT = audioproc.MusicalTime
NOTE_ON = lambda channel, pitch, velocity: bytes([0x90 | channel, pitch, velocity])
NOTE_OFF = lambda channel, pitch: bytes([0x80 | channel, pitch, 0])


class PianoRollGridTest(uitest.UITestCase):
    def setup_testcase(self):
        self.grid = pianoroll.PianoRollGrid()
        self.grid.setReadOnly(False)
        self.grid.setDuration(audioproc.MusicalDuration(8, 4))
        self.grid.resize(600, 400)
        self.setWidgetUnderTest(self.grid)

    def fill_grid(self):
        self.grid.addEvent(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
        self.grid.addEvent(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
        self.grid.addEvent(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
        self.grid.addEvent(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
        self.grid.addEvent(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
        self.grid.addEvent(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
        self.grid.addEvent(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
        self.grid.addEvent(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

    def test_render(self):
        self.fill_grid()
        self.renderWidget()
        self.grid.setOverlayColor(QtGui.QColor(100, 100, 255, 100))
        self.renderWidget()
        self.grid.setPlaybackPosition(MT(3, 4))
        self.renderWidget()

    def test_add_interval(self):
        self.moveMouse(self.grid.pointAt(70, MT(2, 4)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(70, MT(3, 4)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(70, MT(4, 4)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(2, 4), NOTE_ON(0, 70, 100)),
             MEVT(MT(4, 4), NOTE_OFF(0, 70)),
            ])

        self.moveMouse(self.grid.pointAt(70, MT(5, 4)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(70, MT(3, 4)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(2, 4), NOTE_ON(0, 70, 100)),
             MEVT(MT(3, 4), NOTE_OFF(0, 70)),
             MEVT(MT(3, 4), NOTE_ON(0, 70, 100)),
             MEVT(MT(5, 4), NOTE_OFF(0, 70)),
            ])

    def test_move_interval(self):
        self.grid.addEvent(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
        self.grid.addEvent(MEVT(MT(2, 4), NOTE_OFF(0, 60)))

        self.moveMouse(self.grid.pointAt(60, MT(1, 4)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(61, MT(2, 4)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(62, MT(3, 4)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(2, 4), NOTE_ON(0, 62, 100)),
             MEVT(MT(4, 4), NOTE_OFF(0, 62)),
            ])

    def test_delete_interval(self):
        self.grid.addEvent(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
        self.grid.addEvent(MEVT(MT(2, 4), NOTE_OFF(0, 60)))

        self.moveMouse(self.grid.pointAt(60, MT(1, 4)))
        self.pressMouseButton(Qt.MiddleButton)
        self.releaseMouseButton(Qt.MiddleButton)

        self.assertEqual(
            self.grid.events(),
            [])

    def test_resize_interval(self):
        self.grid.addEvent(MEVT(MT(1, 4), NOTE_ON(0, 60, 100)))
        self.grid.addEvent(MEVT(MT(3, 4), NOTE_OFF(0, 60)))

        self.moveMouse(self.grid.pointAt(60, MT(1, 4)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(61, MT(1, 8)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(62, MT(0, 4)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(0, 4), NOTE_ON(0, 60, 100)),
             MEVT(MT(3, 4), NOTE_OFF(0, 60)),
            ])

        self.moveMouse(self.grid.pointAt(60, MT(3, 4)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(61, MT(5, 8)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(62, MT(2, 4)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(0, 4), NOTE_ON(0, 60, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 60)),
            ])

    def test_select_rect(self):
        self.fill_grid()
        self.grid.setEditMode(pianoroll.EditMode.SelectRect)

        self.moveMouse(self.grid.pointAt(50, MT(5, 8)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(60, MT(3, 8)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(70, MT(1, 8)))
        self.releaseMouseButton(Qt.LeftButton)

        self.grid.delete_selection_action.trigger()

        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(3, 4), NOTE_ON(0, 63, 100)),
             MEVT(MT(4, 4), NOTE_OFF(0, 63)),
            ])

    def test_change_velocity(self):
        self.fill_grid()
        self.grid.setEditMode(pianoroll.EditMode.EditVelocity)

        assert self.grid.events()[0].midi[2] == 100

        self.moveMouse(self.grid.pointAt(60, MT(1, 8)))
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(self.grid.pointAt(60, MT(2, 8)))
        self.renderWidget()
        self.moveMouse(self.grid.pointAt(60, MT(3, 8)))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertGreater(self.grid.events()[0].midi[2], 100)

    def test_transpose_selection(self):
        self.fill_grid()
        self.grid.select_all_action.trigger()
        self.grid.transpose_selection_up_octave_action.trigger()
        self.assertEqual(
            self.grid.events(),
            [MEVT(MT(0, 4), NOTE_ON(0, 72, 100)),
             MEVT(MT(1, 4), NOTE_OFF(0, 72)),
             MEVT(MT(1, 4), NOTE_ON(0, 73, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 73)),
             MEVT(MT(2, 4), NOTE_ON(0, 74, 100)),
             MEVT(MT(3, 4), NOTE_OFF(0, 74)),
             MEVT(MT(3, 4), NOTE_ON(0, 75, 100)),
             MEVT(MT(4, 4), NOTE_OFF(0, 75)),
            ])


class PianoKeysTest(uitest.UITestCase):
    def setup_testcase(self):
        self.keys = pianoroll.PianoKeys()
        self.keys.setScrollable(True)
        self.keys.setPlayable(True)
        self.keys.resize(self.keys.minimumWidth(), 200)
        self.setWidgetUnderTest(self.keys)

    def test_notes(self):
        self.keys.noteOn(60)
        self.renderWidget()
        self.keys.noteOn(61)
        self.renderWidget()
        self.keys.noteOff(60)
        self.renderWidget()
        self.keys.noteOff(61)
        self.renderWidget()

    def test_scroll(self):
        self.moveMouse(QtCore.QPoint(20, 100))
        self.pressKey(Qt.Key_Shift)
        self.pressMouseButton(Qt.LeftButton)
        self.moveMouse(QtCore.QPoint(20, 80))
        self.renderWidget()
        self.moveMouse(QtCore.QPoint(20, 60))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(self.keys.yOffset(), 40)

    def test_play(self):
        notes = []  # type: List[pianoroll.PlayNotes]
        self.keys.playNotes.connect(notes.append)

        self.moveMouse(QtCore.QPoint(20, 100))
        self.pressMouseButton(Qt.LeftButton)
        self.renderWidget()
        self.releaseMouseButton(Qt.LeftButton)

        self.assertEqual(len(notes), 2)

        notes.clear()
        self.moveMouse(QtCore.QPoint(20, 100))
        self.pressMouseButton(Qt.LeftButton)
        self.renderWidget()
        self.moveMouse(QtCore.QPoint(20, 180))
        self.releaseMouseButton(Qt.LeftButton)

        self.assertGreater(len(notes), 2)
        self.assertEqual(len(notes) % 2, 0)


class PianoRollTest(uitest.UITestCase):
    def setup_testcase(self):
        self.roll = pianoroll.PianoRoll()
        self.roll.resize(600, 400)
        self.setWidgetUnderTest(self.roll)

    def test_init(self):
        self.renderWidget()
        self.assertTrue(self.roll.close())

    def test_addEvent(self):
        self.roll.addEvent(MEVT(MT(1, 8), NOTE_ON(0, 60, 100)))
        self.renderWidget()
        self.roll.addEvent(MEVT(MT(2, 8), NOTE_OFF(0, 60)))
        self.renderWidget()

    def test_clearEvents(self):
        self.roll.addEvent(MEVT(MT(1, 8), NOTE_ON(0, 60, 100)))
        self.roll.addEvent(MEVT(MT(2, 8), NOTE_OFF(0, 60)))
        self.roll.clearEvents()
        self.renderWidget()
