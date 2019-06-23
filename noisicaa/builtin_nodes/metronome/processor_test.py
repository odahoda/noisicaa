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

import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import constants
from noisicaa.audioproc.public import node_parameters_pb2
from noisicaa.audioproc.public import time_mapper
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_pb2


class ProcessorMetronomeTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.time_mapper = None

    def setup_testcase(self):
        self.time_mapper = time_mapper.PyTimeMapper(self.host_system.sample_rate)
        self.time_mapper.setup()

    def cleanup_testcase(self):
        if self.time_mapper is not None:
            self.time_mapper.cleanup()
            self.time_mapper = None

    def test_value(self):
        plugin_uri = 'builtin://metronome'

        node_desc = self.node_db[plugin_uri]

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.metronome_spec]
        spec.sample_path = os.path.join(constants.DATA_DIR, 'sounds', 'metronome.wav')
        spec.duration.numerator = 1
        spec.duration.denominator = 4
        proc.set_parameters(params)

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        buffer_mgr.allocate('out:left', buffers.PyFloatAudioBlockBuffer())
        buffer_mgr.allocate('out:right', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 0
        ctxt.clear_time_map(self.host_system.block_size)
        for s in range(self.host_system.block_size):
            ctxt.set_sample_time(
                s,
                musical_time.PyMusicalTime(s, 44100),
                musical_time.PyMusicalTime(s + 1, 44100))

        proc.connect_port(ctxt, 0, buffer_mgr.data('out:left'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('out:right'))

        proc.process_block(ctxt, self.time_mapper)
