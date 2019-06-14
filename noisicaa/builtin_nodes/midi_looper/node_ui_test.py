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

from PyQt5 import QtWidgets

from noisidev import uitest
from noisicaa import audioproc
from . import node_ui


class MidiLooperNodeTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-looper')

    async def test_init(self):
        widget = node_ui.MidiLooperNode(node=self.node, context=self.context)
        widget.cleanup()


class MidiLooperNodeWidgetTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-looper')

    async def test_init(self):
        widget = node_ui.MidiLooperNodeWidget(node=self.node, context=self.context)
        widget.cleanup()

    async def test_duration(self):
        widget = node_ui.MidiLooperNodeWidget(node=self.node, context=self.context)
        try:
            duration = widget.findChild(QtWidgets.QSpinBox, 'duration')
            assert duration is not None
            self.assertEqual(duration.value(), (self.node.duration / audioproc.MusicalDuration(1, 4)).numerator)

            with self.project.apply_mutations('test'):
                self.node.set_duration(audioproc.MusicalDuration(5, 4))
            self.assertEqual(audioproc.MusicalDuration(duration.value(), 4), self.node.duration)

            duration.setValue(7)
            self.assertEqual(self.node.duration, audioproc.MusicalDuration(7, 4))

        finally:
            widget.cleanup()
