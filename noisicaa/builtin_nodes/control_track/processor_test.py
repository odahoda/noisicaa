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

import math

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_messages


class ProcessorCVGeneratorTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.proc = None
        self.arena = None
        self.buffer_mgr = None
        self.ctxt = None
        self.outbuf = None

    def setup_testcase(self):
        self.host_system.set_block_size(4096)

        plugin_uri = 'builtin://control-track'
        node_description = self.node_db[plugin_uri]

        self.proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_description)
        self.proc.setup()

        self.buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        self.outbuf = self.buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())

        self.ctxt = block_context.PyBlockContext()

        self.ctxt.clear_time_map(self.host_system.block_size)
        for s in range(self.host_system.block_size):
            self.ctxt.set_sample_time(
                s,
                musical_time.PyMusicalTime(s, 44100),
                musical_time.PyMusicalTime(s + 1, 44100))

        self.proc.connect_port(self.ctxt, 0, self.buffer_mgr.data('out'))

    def cleanup_testcase(self):
        if self.proc is not None:
            self.proc.cleanup()

    def test_empty(self):
        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(all(v == 0.0 for v in self.outbuf))

    def test_single_control_point(self):
        msg = processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, 44100),
            value=0.5)
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(all(math.isclose(v, 0.5) for v in self.outbuf))

    def test_two_control_points(self):
        msg = processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, 44100),
            value=0.2)
        self.proc.handle_message(msg)

        msg = processor_messages.add_control_point(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(3072, 44100),
            value=0.8)
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        # Constant value before first control point.
        self.assertTrue(all(math.isclose(v, 0.2, rel_tol=0.001) for v in self.outbuf[:1024]))

        # Linear ramp up between first and second control points.
        self.assertTrue(all(math.isclose(v, e, rel_tol=0.001)
                            for v, e
                            in zip(self.outbuf[1024:3072],
                                   [0.2 + 0.6 * i / 2048 for i in range(2048)])))

        # Constant value after second control point.
        self.assertTrue(all(math.isclose(v, 0.8, rel_tol=0.001) for v in self.outbuf[3072:]))

    def test_remove_control_point(self):
        msg = processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, 44100),
            value=0.5)
        self.proc.handle_message(msg)

        msg = processor_messages.add_control_point(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(2048, 44100),
            value=1.0)
        self.proc.handle_message(msg)

        msg = processor_messages.remove_control_point(
            node_id='123',
            id=0x0002)
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(all(math.isclose(v, 0.5) for v in self.outbuf))
