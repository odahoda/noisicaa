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
from . import commands


class StepSequencerNodeTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations():
            self.node = self.project.create_node('builtin://step-sequencer')

    async def test_init(self):
        widget = node_ui.StepSequencerNode(node=self.node, context=self.context)
        widget.cleanup()


class StepSequencerNodeWidgetTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations():
            self.node = self.project.create_node('builtin://step-sequencer')

    async def test_init(self):
        widget = node_ui.StepSequencerNodeWidget(node=self.node, context=self.context)
        widget.cleanup()

    async def test_num_steps_changed(self):
        widget = node_ui.StepSequencerNodeWidget(node=self.node, context=self.context)
        try:
            await self.project_client.send_command(commands.update(
                self.node, set_num_steps=4))
        finally:
            widget.cleanup()
