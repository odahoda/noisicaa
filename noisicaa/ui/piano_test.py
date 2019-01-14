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

from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisidev import uitest
from noisicaa import model
from . import piano


class PianoTest(uitest.UITestCase):
    def test_init(self):
        p = piano.PianoWidget(None)
        self.assertTrue(p.close())

    def test_key_events(self):
        p = piano.PianoWidget(None)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)

        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r")
        p.event(evt)
        self.assertEqual(
            on_listener.call_args_list,
            [mock.call(model.Pitch('C5'))])

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyRelease, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r")
        p.event(evt)

        self.assertEqual(
            off_listener.call_args_list,
            [mock.call(model.Pitch('C5'))])

        self.assertTrue(p.close())

    def test_key_events_unused_key(self):
        p = piano.PianoWidget(None)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)
        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r",
            autorep=True)
        p.event(evt)
        on_listener.not_called()

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyRelease, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r",
            autorep=True)
        p.event(evt)
        off_listener.not_called()

        self.assertTrue(p.close())

    def test_key_events_ignore_auto_repeat(self):
        p = piano.PianoWidget(None)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)
        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, Qt.Key_Apostrophe, Qt.NoModifier, 0x14, 0, 0, "'")
        p.event(evt)
        on_listener.not_called()

        evt = QtGui.QKeyEvent(
            QtCore.QEvent.KeyRelease, Qt.Key_Apostrophe, Qt.NoModifier, 0x14, 0, 0, "'")
        p.event(evt)
        off_listener.not_called()

        self.assertTrue(p.close())
