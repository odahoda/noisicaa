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
import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import node_db
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor

logger = logging.getLogger(__name__)


class ProcessorVCATestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def test_json(self):
        node_desc = node_db.faust_json_to_node_description(
            os.path.join(os.path.dirname(__file__), 'processor.json'))
        logger.info(node_desc)

    def test_process_block(self):
        plugin_uri = 'builtin://vca'
        node_description = self.node_db[plugin_uri]

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_description)
        proc.setup()

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        ain = buffer_mgr.allocate('in', buffers.PyFloatAudioBlockBuffer())
        amp = buffer_mgr.allocate('amp', buffers.PyFloatAudioBlockBuffer())
        aout = buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())
        smooth = buffer_mgr.allocate('smooth', buffers.PyFloatControlValueBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('in'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('amp'))
        proc.connect_port(ctxt, 2, buffer_mgr.data('out'))
        proc.connect_port(ctxt, 3, buffer_mgr.data('smooth'))

        for i in range(self.host_system.block_size):
            ain[i] = 0.8
            amp[i] = 0.5
            aout[i] = 0.0
        smooth[0] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper
        self.assertTrue(all(abs(v) - 0.4 < 0.001 for v in aout), [i for i in aout[:16]])

        proc.cleanup()
