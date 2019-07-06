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

from noisidev import uitest
from . import node_ui


class MidiMonitorNodeTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-monitor')

    async def test_init(self):
        widget = node_ui.MidiMonitorNode(node=self.node, context=self.context)
        widget.cleanup()


class MidiMonitorNodeWidgetTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://midi-monitor')

    async def test_init(self):
        widget = node_ui.MidiMonitorNodeWidget(
            node=self.node, session_prefix='test', context=self.context)
        widget.cleanup()
