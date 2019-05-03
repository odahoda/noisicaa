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
from noisicaa import music
from . import model
from . import commands


class InstrumentTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.Instrument:
        await self.client.send_command(music.create_node(
            'builtin://instrument'))
        return cast(model.Instrument, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.Instrument)

    async def test_change_instrument_uri(self):
        node = await self._add_node()

        await self.client.send_command(commands.update(
            node, set_instrument_uri='blabla'))
        self.assertEqual(node.instrument_uri, 'blabla')
