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

from unittest import mock

from PySide2.QtCore import Qt
from PySide2 import QtCore
from PySide2 import QtGui

from noisidev import uitest
from . import canvas


class SceneTest(uitest.ProjectMixin, uitest.UITestCase):
    def setup_testcase(self):
        self.scene = canvas.Scene(context=self.context)

    def test_setZoom(self):
        self.scene.setZoom(0.5)
        self.assertAlmostEqual(self.scene.zoom(), 0.5)


class CanvasTest(uitest.ProjectMixin, uitest.UITestCase):
    def setup_testcase(self):
        self.canvas = canvas.Canvas(context=self.context)
        self.scene = self.canvas.scene()

    def test_wheelEvent_zoom_in(self):
        sig = mock.Mock()
        self.canvas.zoomStarted.connect(sig)

        evt = QtGui.QWheelEvent(
            QtCore.QPointF(200, 100),
            QtCore.QPointF(500, 300),
            QtCore.QPoint(0, 10),
            QtCore.QPoint(0, 120),
            10, Qt.Vertical,
            Qt.NoButton,
            Qt.NoModifier)
        self.canvas.wheelEvent(evt)
        self.assertTrue(evt.isAccepted())

        sig.assert_called()
        zoom, = sig.call_args[0]
        self.assertEqual(zoom.direction, 1)
        self.assertEqual(zoom.center, QtCore.QPointF(200, 100))

    def test_wheelEvent_zoom_out(self):
        sig = mock.Mock()
        self.canvas.zoomStarted.connect(sig)

        evt = QtGui.QWheelEvent(
            QtCore.QPointF(200, 100),
            QtCore.QPointF(500, 300),
            QtCore.QPoint(0, -10),
            QtCore.QPoint(0, -120),
            10, Qt.Vertical,
            Qt.NoButton,
            Qt.NoModifier)
        self.canvas.wheelEvent(evt)
        self.assertTrue(evt.isAccepted())

        sig.assert_called()
        zoom, = sig.call_args[0]
        self.assertEqual(zoom.direction, -1)
        self.assertEqual(zoom.center, QtCore.QPointF(200, 100))

    async def test_mousePressEvent(self):
        self.canvas.resize(400, 300)

        evt = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            QtCore.QPointF(20, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier)
        self.canvas.mousePressEvent(evt)
        self.assertTrue(evt.isAccepted())
