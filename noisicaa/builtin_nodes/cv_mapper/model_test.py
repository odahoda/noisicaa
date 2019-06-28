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


class CVMapperTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.CVMapper:
        with self.project.apply_mutations('test'):
            return cast(
                model.CVMapper,
                self.project.create_node('builtin://cv-mapper'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.CVMapper)
