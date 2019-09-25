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

from typing import Any, Dict

from noisidev import unittest
from noisidev import unittest_mixins
from . import loadtest_generator
from . import project


class LoadTestGeneratorTest(
        unittest_mixins.NodeDBMixin,
        unittest.AsyncTestCase):
    def setup_testcase(self):
        self.pool = project.Pool()

    async def test_empty_project(self):
        spec = {
            'bpm': 137,
        }  # type: Dict[str, Any]
        p = loadtest_generator.create_loadtest_project(
            spec=spec,
            pool=self.pool,
            project_cls=project.BaseProject,
            node_db=self.node_db)
        self.assertEqual(len(p.nodes), 2)
        self.assertEqual(p.nodes[0].description.uri, 'builtin://sink')
        self.assertEqual(p.nodes[1].description.uri, 'builtin://mixer')
        self.assertEqual(p.nodes[1].name, 'Master')
        self.assertEqual(p.bpm, 137)

    async def test_presets(self):
        for name, spec in loadtest_generator.PRESETS.items():
            with self.subTest(name):
                loadtest_generator.create_loadtest_project(
                    spec=spec,
                    pool=project.Pool(),
                    project_cls=project.BaseProject,
                    node_db=self.node_db)
