#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import unittest
import struct

from . cimport lilv
from . import lv2
from . import sratom

logger = logging.getLogger(__name__)


class NodeTest(unittest.TestCase):
    def setUp(self):
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
    def setUp(self):
        self.world = lilv.World()
        self.world.load_all()
        self.plugins = self.world.get_all_plugins()

    def test_features(self):
        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-fifths')
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
            cdef bytearray in_buf
            cdef bytearray out_buf
            cdef bytearray gain_buf

        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-amp')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))
        gain_port = plugin.get_port_by_symbol(self.world.new_string('gain'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        in_buf = bytearray(4096)
        instance.connect_port(in_port.get_index(), <char*>in_buf)

        out_buf = bytearray(4096)
        instance.connect_port(out_port.get_index(), <char*>out_buf)

        gain_buf = bytearray(4)
        instance.connect_port(gain_port.get_index(), <char*>gain_buf)

        instance.activate()
        instance.run(1024)
        instance.deactivate()

    def test_instantiate_amp(self):
        cdef:
            cdef lilv.Instance instance
            cdef bytearray in_buf
            cdef bytearray out_buf
            cdef bytearray gain_buf

        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-amp')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))
        gain_port = plugin.get_port_by_symbol(self.world.new_string('gain'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        in_buf = bytearray(4096)
        instance.connect_port(in_port.get_index(), <char*>in_buf)

        out_buf = bytearray(4096)
        instance.connect_port(out_port.get_index(), <char*>out_buf)

        gain_buf = bytearray(4)
        instance.connect_port(gain_port.get_index(), <char*>gain_buf)

        instance.activate()
        instance.run(1024)
        instance.deactivate()

    def test_instantiate_midigate(self):
        cdef:
            cdef lilv.Instance instance

        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-midigate')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        control_port = plugin.get_port_by_symbol(self.world.new_string('control'))
        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        control_buf = bytearray(1024)
        instance.connect_port(control_port.get_index(), <char*>control_buf)

        forge = lv2.AtomForge(self.world.urid_mapper)
        forge.set_buffer(control_buf, 1024)
        with forge.sequence():
            forge.write_midi_event(3, bytes([0b10010000, 65, 127]), 3)
            forge.write_midi_event(7, bytes([0b10000000, 65, 0]), 3)

        logger.info(sratom.atom_to_turtle(self.world.urid_mapper, control_buf))

        in_buf = struct.pack('=ffffffffff', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        instance.connect_port(in_port.get_index(), <char*>in_buf)

        out_buf = bytearray(40)
        instance.connect_port(out_port.get_index(), <char*>out_buf)

        instance.activate()
        instance.run(10)
        instance.deactivate()

        # The output should rather be [0, 0, 0, 4, 5, 6, 7, 0, 0, 0], but eg-midigate does not
        # work correctly.
        self.assertEqual(
            out_buf,
            struct.pack('=ffffffffff', 1, 2, 3, 0, 0, 0, 0, 0, 0, 0))

    def test_instantiate_fifths(self):
        cdef:
            cdef lilv.Instance instance

        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-fifths')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        in_buf = bytearray(1024)
        instance.connect_port(in_port.get_index(), <char*>in_buf)

        forge = lv2.AtomForge(self.world.urid_mapper)
        forge.set_buffer(in_buf, 1024)
        with forge.sequence():
            forge.write_midi_event(3, bytes([0b10010000, 65, 127]), 3)
            forge.write_midi_event(8, bytes([0b10000000, 65, 0]), 3)

        logger.info(sratom.atom_to_turtle(self.world.urid_mapper, in_buf))

        out_buf = bytearray(1024)
        instance.connect_port(out_port.get_index(), <char*>out_buf)

        instance.activate()
        instance.run(1024)
        instance.deactivate()

        logger.info(sratom.atom_to_turtle(self.world.urid_mapper, out_buf))

        # TODO: verify that out_buf contains 4 midi events.

    def test_instantiate_(self):
        cdef:
            cdef lilv.Instance instance

        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-fifths')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        in_buf = bytearray(1024)
        instance.connect_port(in_port.get_index(), <char*>in_buf)

        forge = lv2.AtomForge(self.world.urid_mapper)
        forge.set_buffer(in_buf, 1024)
        with forge.sequence():
            forge.write_midi_event(3, bytes([0b10010000, 65, 127]), 3)
            forge.write_midi_event(8, bytes([0b10000000, 65, 0]), 3)

        logger.info(sratom.atom_to_turtle(self.world.urid_mapper, in_buf))

        out_buf = bytearray(1024)
        instance.connect_port(out_port.get_index(), <char*>out_buf)

        instance.activate()
        instance.run(1024)
        instance.deactivate()

        logger.info(sratom.atom_to_turtle(self.world.urid_mapper, out_buf))

        # TODO: verify that out_buf contains 4 midi events.
