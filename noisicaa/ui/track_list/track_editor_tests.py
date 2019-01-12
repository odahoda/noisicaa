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

# mypy: loose

import contextlib
from fractions import Fraction
from unittest import mock
from typing import List, Set

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisidev import uitest
from noisicaa.ui import player_state


class HIDState(object):
    def __init__(self):
        self.__pressed_keys = set()  # type: Set[Qt.Key]
        self.__pressed_mouse_buttons = set()  # type: Set[Qt.MouseButton]
        self.__mouse_pos = QtCore.QPointF(0, 0)

    @property
    def window_pos(self):
        return QtCore.QPointF(100, 200)

    def press_mouse_button(self, button):
        assert button not in self.__pressed_mouse_buttons
        self.__pressed_mouse_buttons.add(button)

    def release_mouse_button(self, button):
        assert button in self.__pressed_mouse_buttons
        self.__pressed_mouse_buttons.remove(button)

    def set_mouse_pos(self, pos):
        self.__mouse_pos = pos

    @property
    def mouse_pos(self):
        return self.__mouse_pos

    @property
    def mouse_buttons(self):
        buttons = Qt.NoButton
        for button in self.__pressed_mouse_buttons:
            buttons |= button
        return buttons

    def press_key(self, key):
        assert key not in self.__pressed_keys
        self.__pressed_keys.add(key)

    def release_key(self, key):
        assert key in self.__pressed_keys
        self.__pressed_keys.remove(key)

    @property
    def modifiers(self):
        modifiers = Qt.KeyboardModifiers()
        for key in self.__pressed_keys:
            if key == Qt.Key_Shift:
                modifiers |= Qt.ShiftModifier
            elif key == Qt.Key_Control:
                modifiers |= Qt.ControlModifier
            elif key == Qt.Key_Alt:
                modifiers |= Qt.AltModifier
            elif key == Qt.Key_Meta:
                modifiers |= Qt.MetaModifier

        return modifiers


class Event(object):
    def replay(self, state, widget):
        raise NotImplementedError

class MoveMouse(Event):
    def __init__(self, x, y):
        self.__x = x
        self.__y = y

    def replay(self, state, widget):
        state.set_mouse_pos(QtCore.QPointF(self.__x, self.__y))
        widget.mouseMoveEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(self.__x, self.__y),
            QtCore.QPointF(self.__x, self.__y) + widget.viewTopLeft(),
            QtCore.QPointF(self.__x, self.__y) + widget.viewTopLeft() + state.window_pos,
            Qt.NoButton,
            state.mouse_buttons,
            state.modifiers))


class PressMouseButton(Event):
    def __init__(self, button):
        self.__button = button

    def replay(self, state, widget):
        state.press_mouse_button(self.__button)
        widget.mousePressEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))


class DoubleClickButton(Event):
    def __init__(self, button):
        self.__button = button

    def replay(self, state, widget):
        state.press_mouse_button(self.__button)
        widget.mousePressEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))
        widget.mouseReleaseEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))
        widget.mouseDoubleClickEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonDblClick,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))
        widget.mouseReleaseEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))


class ReleaseMouseButton(Event):
    def __init__(self, button):
        self.__button = button

    def replay(self, state, widget):
        state.release_mouse_button(self.__button)
        widget.mouseReleaseEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft(),
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            self.__button,
            state.mouse_buttons,
            state.modifiers))


class MoveWheel(Event):
    def __init__(self, steps):
        self.__steps = steps

    def replay(self, state, widget):
        widget.wheelEvent(QtGui.QWheelEvent(
            state.mouse_pos,
            state.mouse_pos + widget.viewTopLeft() + state.window_pos,
            QtCore.QPoint(0, 10 * self.__steps),
            QtCore.QPoint(0, 15 * self.__steps),
            0, Qt.Vertical,
            state.mouse_buttons,
            state.modifiers))


class PressKey(Event):
    def __init__(self, key):
        self.__key = key

    def replay(self, state, widget):
        state.press_key(self.__key)
        widget.keyPressEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            self.__key,
            state.modifiers,
            0,
            0,
            0,
            '',
            False,
            0))


class ReleaseKey(Event):
    def __init__(self, key):
        self.__key = key

    def replay(self, state, widget):
        state.release_key(self.__key)
        widget.keyReleaseEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyRelease,
            self.__key,
            state.modifiers,
            0,
            0,
            0,
            '',
            False,
            0))


class TrackEditorItemTestMixin(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        self.player_state = player_state.PlayerState(context=self.context)
        self.tool_box = None
        self.editor = mock.Mock()
        self.editor.currentToolBox.side_effect = lambda: self.tool_box

        self.__hid_state = HIDState()

    def _createTrackItem(self, **kwargs):
        raise NotImplementedError

    @contextlib.contextmanager
    def _trackItem(self, **kwargs):
        ti = self._createTrackItem(**kwargs)
        try:
            yield ti
        finally:
            ti.close()

    def _replay_events(self, widget, events):
        for event in events:
            event.replay(self.__hid_state, widget)

    def test_properties(self):
        with self._trackItem() as ti:
            self.assertIs(ti.track, self.project.master_group.tracks[0])

    def test_isCurrent(self):
        with self._trackItem() as ti:
            ti.setSize(QtCore.QSize(200, 100))

            rects = []  # type: List[QtCore.QRect]
            ti.rectChanged.connect(rects.append)

            self.assertFalse(ti.isCurrent())

            ti.setIsCurrent(True)
            self.assertTrue(ti.isCurrent())
            self.assertEqual(rects, [QtCore.QRect(0, 0, 200, 100)])

            rects.clear()
            ti.setIsCurrent(True)
            self.assertTrue(ti.isCurrent())
            self.assertEqual(rects, [])

    def test_scale(self):
        with self._trackItem() as ti:
            self.assertEqual(ti.scaleX(), Fraction(500, 1))
            ti.setScaleX(Fraction(1000, 1))
            self.assertEqual(ti.scaleX(), Fraction(1000, 1))

    def test_size(self):
        with self._trackItem() as ti:
            ti.setSize(QtCore.QSize(100, 200))
            self.assertEqual(ti.size(), QtCore.QSize(100, 200))
            self.assertEqual(ti.width(), 100)
            self.assertEqual(ti.height(), 200)
            ti.setWidth(300)
            self.assertEqual(ti.size(), QtCore.QSize(300, 200))
            self.assertEqual(ti.width(), 300)
            self.assertEqual(ti.height(), 200)
            ti.setHeight(400)
            self.assertEqual(ti.size(), QtCore.QSize(300, 400))
            self.assertEqual(ti.width(), 300)
            self.assertEqual(ti.height(), 400)

    def test_sizeChanged(self):
        with self._trackItem() as ti:
            sizes = []  # type: List[QtCore.QSize]
            ti.sizeChanged.connect(sizes.append)
            ti.setSize(QtCore.QSize(100, 200))
            ti.setWidth(300)
            ti.setHeight(400)
            ti.setSize(QtCore.QSize(300, 400))
            self.assertEqual(
                sizes,
                [QtCore.QSize(100, 200), QtCore.QSize(300, 200), QtCore.QSize(300, 400)])

    def test_viewRect(self):
        with self._trackItem() as ti:
            ti.setSize(QtCore.QSize(150, 50))
            ti.setViewTopLeft(QtCore.QPoint(100, 200))
            self.assertEqual(ti.viewTopLeft(), QtCore.QPoint(100, 200))
            self.assertEqual(ti.viewLeft(), 100)
            self.assertEqual(ti.viewTop(), 200)
            self.assertEqual(ti.viewRect(), QtCore.QRect(100, 200, 150, 50))

    def test_mouse_events(self):
        with self._trackItem() as ti:
            self._replay_events(
                ti,
                [MoveMouse(100, 50),
                 PressMouseButton(Qt.LeftButton),
                 MoveMouse(110, 54),
                 ReleaseMouseButton(Qt.LeftButton),
                 MoveMouse(150, 30),
                 MoveWheel(-1),
                 MoveMouse(180, 60),
                 DoubleClickButton(Qt.LeftButton),
                ])

    def test_key_events(self):
        with self._trackItem() as ti:
            self._replay_events(
                ti,
                [MoveMouse(100, 50),
                 PressKey(Qt.Key_Shift),
                 PressKey(Qt.Key_A),
                 ReleaseKey(Qt.Key_A),
                 ReleaseKey(Qt.Key_Shift),
                ])

    def test_buildContextMenu(self):
        with self._trackItem() as ti:
            menu = QtWidgets.QMenu()
            ti.buildContextMenu(menu, QtCore.QPoint(100, 50))

    def test_paint(self):
        with self._trackItem() as ti:
            ti.setSize(QtCore.QSize(200, 100))

            img = QtGui.QImage(ti.size(), QtGui.QImage.Format_RGB32)
            painter = QtGui.QPainter(img)
            try:
                img.fill(Qt.black)
                ti.paint(painter, ti.viewRect())
                self.assertEqual(QtGui.QColor(img.pixel(0, 0)), QtGui.QColor(Qt.white))

                img.fill(Qt.black)
                ti.setIsCurrent(True)
                ti.paint(painter, ti.viewRect())
                self.assertEqual(QtGui.QColor(img.pixel(0, 0)), QtGui.QColor(240, 240, 255))
            finally:
                painter.end()
                painter = None  # QPainter must be destroyed before QImage.
                img = None
