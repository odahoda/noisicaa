#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import logging
import struct

from noisidev import unittest
from . cimport lilv
from . import sratom

logger = logging.getLogger(__name__)


class NodeTest(unittest.TestCase):
    def setup_testcase(self):
        self.world = lilv.World()

    def test_string(self):
        n = self.world.new_string('foo')
        self.assertIsInstance(n, lilv.Node)
        self.assertTrue(n.is_string)
        self.assertEqual(n, 'foo')
        self.assertEqual(str(n), 'foo')

    def test_uri(self):
        n = self.world.new_uri('http://foo/bar')
        self.assertIsInstance(n, lilv.Node)
        self.assertTrue(n.is_uri)
        self.assertEqual(n, 'http://foo/bar')
        self.assertEqual(str(n), 'http://foo/bar')

    def test_float(self):
        n = self.world.new_float(2.0)
        self.assertIsInstance(n, lilv.Node)
        self.assertTrue(n.is_float)
        self.assertEqual(n, 2.0)
        self.assertEqual(float(n), 2.0)

    def test_int(self):
        n = self.world.new_float(2)
        self.assertIsInstance(n, lilv.Node)
        self.assertTrue(n.is_int)
        self.assertEqual(n, 2)
        self.assertEqual(int(n), 2)

    def test_int(self):
        n = self.world.new_bool(True)
        self.assertIsInstance(n, lilv.Node)
        self.assertTrue(n.is_bool)
        self.assertEqual(n, True)
        self.assertEqual(bool(n), True)

    def test_compare(self):
        n1 = self.world.new_string('foo')
        n2 = self.world.new_string('foo')
        n3 = self.world.new_string('bar')

        self.assertTrue(n1 == n2)
        self.assertFalse(n1 != n2)
        self.assertFalse(n1 == n3)
        self.assertTrue(n1 != n3)


class WorldTest(unittest.TestCase):
    def test_ns(self):
        world = lilv.World()
        self.assertIsInstance(world.ns.lilv.map, lilv.BaseNode)
        self.assertEqual(str(world.ns.lilv.map), 'http://drobilla.net/ns/lilv#map')

    def test_get_all_plugins(self):
        world = lilv.World()
        world.load_all()
        for plugin in world.get_all_plugins():
            self.assertIsInstance(plugin.get_uri(), lilv.BaseNode)


class PluginTest(unittest.TestCase):
    def setup_testcase(self):
        self.world = lilv.World()
        self.world.load_all()
        self.plugins = self.world.get_all_plugins()

    def test_features(self):
        uri_node = self.world.new_uri('http://noisicaa.odahoda.de/plugins/test-passthru')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)

        self.assertEqual(
            plugin.required_features,
            ['http://lv2plug.in/ns/ext/urid#map'])
        self.assertEqual(
            plugin.optional_features,
            ['http://lv2plug.in/ns/lv2core#hardRTCapable'])

    # def test_not_supported(self):
    #     uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-sampler')
    #     plugin = self.plugins.get_by_uri(uri_node)
    #     self.assertIsNot(plugin, None)

    #     self.assertEqual(
    #         sorted(str(f) for f in plugin.get_missing_features()),
    #         ['http://lv2plug.in/ns/ext/state#loadDefaultState'])
