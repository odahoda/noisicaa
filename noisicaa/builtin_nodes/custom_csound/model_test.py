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


class CustomCSoundTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.CustomCSound:
        with self.project.apply_mutations():
            return cast(
                model.CustomCSound,
                self.project.create_node('builtin://custom-csound'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.CustomCSound)

    async def test_create_port(self):
        node = await self._add_node()

        with self.project.apply_mutations():
            node.create_port(0, 'foo')
        self.assertEqual(len(node.ports), 1)

    async def test_delete_port(self):
        node = await self._add_node()
        with self.project.apply_mutations():
            port = node.create_port(0, 'foo')

        with self.project.apply_mutations():
            node.delete_port(port)
        self.assertEqual(len(node.ports), 0)
