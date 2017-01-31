#!/usr/bin/python3

import unittest

import numpy

from . import lilv


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

    def test_not_supported(self):
        uri_node = self.world.new_uri('http://guitarix.sourceforge.net/plugins/gx_cabinet#CABINET')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)

        self.assertEqual(
            sorted(str(f) for f in plugin.get_missing_features()),
            ['http://lv2plug.in/ns/ext/buf-size#boundedBlockLength',
             'http://lv2plug.in/ns/ext/worker#schedule'])

    def test_instantiate(self):
        uri_node = self.world.new_uri('http://lv2plug.in/plugins/eg-amp')
        plugin = self.plugins.get_by_uri(uri_node)
        self.assertIsNot(plugin, None)
        self.assertEqual(plugin.get_uri(), uri_node)

        in_port = plugin.get_port_by_symbol(self.world.new_string('in'))
        out_port = plugin.get_port_by_symbol(self.world.new_string('out'))
        gain_port = plugin.get_port_by_symbol(self.world.new_string('gain'))

        instance = plugin.instantiate(44100)
        self.assertIsNot(instance, None)

        in_buf = numpy.zeros(shape=(1024,), dtype=numpy.float32)
        instance.connect_port(in_port.get_index(), in_buf)

        out_buf = numpy.zeros(shape=(1024,), dtype=numpy.float32)
        instance.connect_port(out_port.get_index(), out_buf)

        gain_buf = numpy.zeros(shape=(1,), dtype=numpy.float32)
        instance.connect_port(gain_port.get_index(), gain_buf)

        instance.activate()
        instance.run(1024)
        instance.deactivate()
