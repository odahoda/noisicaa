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

import logging
import struct

from noisidev import unittest
from noisicaa.audioproc.public import plugin_state_pb2
from . import plugin_host_test

logger = logging.getLogger(__name__)


class PluginHostLV2Test(plugin_host_test.PluginHostMixin, unittest.TestCase):
    def test_process_block(self):
        plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
        block_size = 256

        with self.setup_plugin(block_size, plugin_uri) as (plugin, bufp):
            for s in range(block_size):
                bufp['audio_in'][s] = 0.5
                bufp['audio_out'][s] = 0.0

            plugin.process_block(block_size)

            for s in range(block_size):
                self.assertAlmostEqual(bufp['audio_in'][s], 0.5, places=2)
                self.assertAlmostEqual(bufp['audio_out'][s], 0.5, places=2)

    def test_state(self):
        plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-state'
        block_size = 256

        with self.setup_plugin(block_size, plugin_uri) as (plugin, _):
            state = plugin.get_state()
            logger.info("State:\n%s", state)
            self.assertIsInstance(state, plugin_state_pb2.PluginState)
            self.assertEqual(len(state.lv2.properties), 1)
            self.assertEqual(
                state.lv2.properties[0].key, 'http://noisicaa.odahoda.de/plugins/test-state#foo')
            self.assertEqual(
                state.lv2.properties[0].type, 'http://lv2plug.in/ns/ext/atom#Number')
            self.assertEqual(
                struct.unpack('!I', state.lv2.properties[0].value)[0], 0x75391654)
