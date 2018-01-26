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
from . import lv2
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
            list(plugin.get_required_features()),
            ['http://lv2plug.in/ns/ext/urid#map'])
        self.assertEqual(
            list(plugin.get_optional_features()),
            ['http://lv2plug.in/ns/lv2core#hardRTCapable'])

        self.assertEqual(plugin.get_missing_features(), [])

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

    # def test_not_supported(self):
    #     uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-sampler')
    #     plugin = self.plugins.get_by_uri(uri_node)
    #     self.assertIsNot(plugin, None)

    #     self.assertEqual(
    #         sorted(str(f) for f in plugin.get_missing_features()),
    #         ['http://lv2plug.in/ns/ext/state#loadDefaultState'])

    def test_instantiate(self):
        cdef:
            cdef lilv.Instance instance
            cdef bytearray audio_in
            cdef bytearray audio_out
            cdef bytearray midi_in
            cdef bytearray midi_out

        uri_node = self.world.new_uri('http://noisicaa.odahoda.de/plugins/test-passthru')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        audio_in_port = plugin.get_port_by_symbol(self.world.new_string('audio_in'))
        audio_out_port = plugin.get_port_by_symbol(self.world.new_string('audio_out'))
        midi_in_port = plugin.get_port_by_symbol(self.world.new_string('midi_in'))
        midi_out_port = plugin.get_port_by_symbol(self.world.new_string('midi_out'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        audio_in = bytearray(4096)
        instance.connect_port(audio_in_port.get_index(), <char*>audio_in)

        audio_out = bytearray(4096)
        instance.connect_port(audio_out_port.get_index(), <char*>audio_out)

        midi_in = bytearray(4096)
        instance.connect_port(midi_in_port.get_index(), <char*>midi_in)

        midi_out = bytearray(4096)
        instance.connect_port(midi_out_port.get_index(), <char*>midi_out)

        instance.activate()
        instance.run(1024)
        instance.deactivate()
