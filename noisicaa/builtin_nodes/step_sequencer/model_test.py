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

from typing import cast

from noisidev import unittest
from noisidev import unittest_mixins
from . import model


class StepSequencerTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.StepSequencer:
        with self.project.apply_mutations('test'):
            return cast(
                model.StepSequencer,
                self.project.create_node('builtin://step-sequencer'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.StepSequencer)
        self.assertFalse(node.time_synched)
        self.assertEqual(len(node.channels), 1)
        self.assertEqual(len(node.channels[0].steps), node.num_steps)

    async def test_set_num_steps_increase(self):
        node = await self._add_node()
        with self.project.apply_mutations('test'):
            node.set_num_steps(13)
        self.assertEqual(node.num_steps, 13)
        self.assertEqual(len(node.channels[0].steps), 13)

    async def test_set_num_steps_decrease(self):
        node = await self._add_node()
        with self.project.apply_mutations('test'):
            node.set_num_steps(5)
        self.assertEqual(node.num_steps, 5)
        self.assertEqual(len(node.channels[0].steps), 5)

    async def test_add_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        with self.project.apply_mutations('test'):
            node.create_channel(0)
        self.assertIs(node.channels[1], old_channel)
        self.assertEqual(len(node.channels), 2)
        self.assertEqual(len(node.channels[0].steps), node.num_steps)

    async def test_delete_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        with self.project.apply_mutations('test'):
            channel = node.create_channel(0)
        with self.project.apply_mutations('test'):
            node.delete_channel(channel)
        self.assertEqual(len(node.channels), 1)
        self.assertIs(node.channels[0], old_channel)
