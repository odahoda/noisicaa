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

from PyQt5 import QtGui

from noisidev import uitest
from noisicaa import audioproc
from noisicaa import value_types
from . import pianoroll


class PianoRollTest(uitest.UITestCase):
    def setup_testcase(self):
        self.roll = pianoroll.PianoRoll()
        self.roll.resize(600, 400)

    def render(self):
        pixmap = QtGui.QPixmap(self.roll.size())
        self.roll.render(pixmap)

    def test_init(self):
        self.render()
        self.assertTrue(self.roll.close())

    def test_addEvent(self):
        self.roll.addEvent(value_types.MidiEvent(
            audioproc.MusicalTime(1, 8), bytes([0x90, 60, 100])))
        self.render()
        self.roll.addEvent(value_types.MidiEvent(
            audioproc.MusicalTime(2, 8), bytes([0x80, 60, 0])))
        self.render()

    def test_clearEvents(self):
        self.roll.addEvent(value_types.MidiEvent(
            audioproc.MusicalTime(1, 8), bytes([0x90, 60, 100])))
        self.roll.addEvent(value_types.MidiEvent(
            audioproc.MusicalTime(2, 8), bytes([0x80, 60, 0])))
        self.roll.clearEvents()
        self.render()
