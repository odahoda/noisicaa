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

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from noisidev import uitest
from . import node_ui


class MidiCCtoCVNodeTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-cc-to-cv')

    async def test_init(self):
        widget = node_ui.MidiCCtoCVNode(node=self.node, context=self.context)
        widget.cleanup()


class MidiCCtoCVNodeWidgetTest(uitest.ProjectMixin, uitest.UITestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widget = None

    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-cc-to-cv')

        self.widget = node_ui.MidiCCtoCVNodeWidget(node=self.node, context=self.context)

    async def cleanup_testcase(self):
        if self.widget is not None:
            self.widget.cleanup()

    async def test_channel_added(self):
        with self.project.apply_mutations('test'):
            self.node.create_channel(1)
        self.assertIsNotNone(self.widget.findChild(
            QtWidgets.QWidget,
            "channel[%016x]:min_value" % self.node.channels[1].id,
            Qt.FindChildrenRecursively))

    async def test_channel_removed(self):
        with self.project.apply_mutations('test'):
            channel = self.node.create_channel(1)

        with self.project.apply_mutations('test'):
            self.node.delete_channel(channel)
        self.assertIsNone(self.widget.findChild(
            QtWidgets.QWidget,
            "channel[%016x]:min_value" % channel.id,
            Qt.FindChildrenRecursively))

    def _getEditor(self, cls, channel, field):
        editor_name = "channel[%016x]:%s" % (channel.id, field)
        editor = self.widget.findChild(cls, editor_name, Qt.FindChildrenRecursively)
        assert editor is not None, editor_name
        return editor

    async def test_channel_midi_channel_changed(self):
        with self.project.apply_mutations('test'):
            self.node.channels[0]. midi_channel = 12

        editor = self._getEditor(QtWidgets.QSpinBox, self.node.channels[0], 'midi_channel')
        self.assertEqual(editor.value(), 12)

    async def test_channel_midi_controller_changed(self):
        with self.project.apply_mutations('test'):
            self.node.channels[0].midi_controller = 63

        editor = self._getEditor(QtWidgets.QSpinBox, self.node.channels[0], 'midi_controller')
        self.assertEqual(editor.value(), 63)

    async def test_channel_min_value_changed(self):
        with self.project.apply_mutations('test'):
            self.node.channels[0].min_value = 440.0

        editor = self._getEditor(QtWidgets.QLineEdit, self.node.channels[0], 'min_value')
        self.assertEqual(editor.text(), '440.0')

    async def test_channel_max_value_changed(self):
        with self.project.apply_mutations('test'):
            self.node.channels[0].max_value = 880.0

        editor = self._getEditor(QtWidgets.QLineEdit, self.node.channels[0], 'max_value')
        self.assertEqual(editor.text(), '880.0')

    # crashes, because test doesn't have a ProjectView
    # async def test_channel_learn_clicked(self):
    #     button = self._getEditor(QtWidgets.QAbstractButton, self.node.channels[0], 'learn')
    #     button.click()
