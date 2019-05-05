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
from noisicaa.music import commands_test
from . import model


class MidiCCtoCVTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.MidiCCtoCV:
        with self.project.apply_mutations():
            return cast(
                model.MidiCCtoCV,
                self.project.create_node('builtin://midi-cc-to-cv'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.MidiCCtoCV)

    async def test_create_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        with self.project.apply_mutations():
            node.create_channel(0)
        self.assertIs(node.channels[1], old_channel)
        self.assertEqual(len(node.channels), 2)

    async def test_delete_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        with self.project.apply_mutations():
            channel = node.create_channel(0)
        with self.project.apply_mutations():
            node.delete_channel(channel)
        self.assertEqual(len(node.channels), 1)
        self.assertIs(node.channels[0], old_channel)
