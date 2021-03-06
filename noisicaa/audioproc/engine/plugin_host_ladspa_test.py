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

from noisidev import unittest
from . import plugin_host_test


class PluginHostLadspaTest(plugin_host_test.PluginHostMixin, unittest.TestCase):
    def test_process_block(self):
        plugin_uri = 'ladspa://passthru.so/passthru'
        block_size = 256

        with self.setup_plugin(block_size, plugin_uri) as (plugin, bufp):
            for s in range(block_size):
                bufp['audio_in'][s] = 0.5
                bufp['audio_out'][s] = 0.0

            plugin.process_block(block_size)

            for s in range(block_size):
                self.assertAlmostEqual(bufp['audio_in'][s], 0.5, places=2)
                self.assertAlmostEqual(bufp['audio_out'][s], 0.5, places=2)
