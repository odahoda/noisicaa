#!/usr/bin/python3

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

import contextlib
from fractions import Fraction

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisidev import uitest
from noisicaa.ui import player_state
from . import editor


class TrackEditorItemTestMixin(uitest.ProjectMixin, uitest.UITestCase):
    def setup_testcase(self):
        self.player_state = player_state.PlayerState(context=self.context)
        self.editor = editor.Editor(player_state=self.player_state, context=self.context)

    def cleanup_testcase(self):
        self.editor.cleanup()

    def _createTrackItem(self, **kwargs):
        raise NotImplementedError

    @contextlib.contextmanager
    def _trackItem(self, **kwargs):
        ti = self._createTrackItem(**kwargs)
        try:
            ti.resize(800, ti.minimumHeight())
            self.setWidgetUnderTest(ti)
            ti.show()
            self.processQtEvents()
            yield ti
        finally:
            ti.cleanup()

    def test_isCurrent(self):
        with self._trackItem() as ti:
            self.assertFalse(ti.isCurrent())

            ti.setIsCurrent(True)
            self.assertTrue(ti.isCurrent())

    def test_scale(self):
        with self._trackItem() as ti:
            self.assertEqual(ti.scaleX(), Fraction(500, 1))
            ti.setScaleX(Fraction(1000, 1))
            self.assertEqual(ti.scaleX(), Fraction(1000, 1))

    def test_mouse_events(self):
        with self._trackItem() as ti:
            self.replayEvents(
                uitest.MoveMouse(QtCore.QPoint(100, 50)),
                uitest.PressMouseButton(Qt.LeftButton),
                uitest.MoveMouse(QtCore.QPoint(110, 54)),
                uitest.ReleaseMouseButton(Qt.LeftButton),
                uitest.MoveMouse(QtCore.QPoint(150, 30)),
                uitest.MoveWheel(-1),
                uitest.MoveMouse(QtCore.QPoint(180, 60)),
                uitest.DoubleClickButton(Qt.LeftButton),
            )

    def test_key_events(self):
        with self._trackItem() as ti:
            self.replayEvents(
                uitest.MoveMouse(QtCore.QPoint(100, 50)),
                uitest.PressKey(Qt.Key_Shift),
                uitest.PressKey(Qt.Key_A),
                uitest.ReleaseKey(Qt.Key_A),
                uitest.ReleaseKey(Qt.Key_Shift),
            )

    def test_buildContextMenu(self):
        with self._trackItem() as ti:
            menu = QtWidgets.QMenu()
            ti.buildContextMenu(menu, QtCore.QPoint(100, 50))

    def test_paint(self):
        with self._trackItem() as ti:
            ti.resize(QtCore.QSize(200, 100))
            self.renderWidget()

            ti.setIsCurrent(True)
            self.renderWidget()
