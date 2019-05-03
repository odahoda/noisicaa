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


class CustomCSoundTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.CustomCSound:
        await self.client.send_command(music.create_node(
            'builtin://custom-csound'))
        return cast(model.CustomCSound, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.CustomCSound)

    async def test_update_orchestra(self):
        node = await self._add_node()

        await self.client.send_command(commands.update(
            node, set_orchestra='blabla'))
        self.assertEqual(node.orchestra, 'blabla')

    async def test_update_score(self):
        node = await self._add_node()

        await self.client.send_command(commands.update(
            node, set_score='blabla'))
        self.assertEqual(node.score, 'blabla')

    async def test_create_port(self):
        node = await self._add_node()

        await self.client.send_command(commands.create_port(node, name='foo'))
        self.assertEqual(len(node.ports), 1)

    async def test_update_port(self):
        node = await self._add_node()
        await self.client.send_command(commands.create_port(node, name='foo'))
        port = node.ports[-1]

        await self.client.send_command(commands.update_port(port, set_csound_name='foo'))
        self.assertEqual(port.csound_name, 'foo')

    async def test_delete_port(self):
        node = await self._add_node()
        await self.client.send_command(commands.create_port(node, name='foo'))
        port = node.ports[-1]

        await self.client.send_command(commands.delete_port(port))
        self.assertEqual(len(node.ports), 0)
