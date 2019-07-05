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

import math

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa.audioproc.public import musical_time
from . import processor_messages


class ProcessorCVGeneratorTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.node_description = self.node_db['builtin://control-track']
        self.host_system.set_block_size(4096)
        self.create_processor()

    def test_empty(self):
        self.process_block()
        self.assertBufferIsQuiet('out')

    def test_single_control_point(self):
        self.processor.handle_message(processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, self.host_system.sample_rate),
            value=0.5))

        self.process_block()
        self.assertBufferAllEqual('out', 0.5)

    def test_two_control_points(self):
        self.processor.handle_message(processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, self.host_system.sample_rate),
            value=0.2))
        self.processor.handle_message(processor_messages.add_control_point(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(3072, self.host_system.sample_rate),
            value=0.8))

        self.process_block()

        # Constant value before first control point.
        self.assertBufferRangeEqual('out', 0, 1024, 0.2)

        # Linear ramp up between first and second control points.
        self.assertTrue(all(math.isclose(v, e, rel_tol=0.001)
                            for v, e
                            in zip(self.buffers['out'][1024:3072],
                                   [0.2 + 0.6 * i / 2048 for i in range(2048)])))

        # Constant value after second control point.
        self.assertBufferRangeEqual('out', 3072, 4096, 0.8)

    def test_remove_control_point(self):
        self.processor.handle_message(processor_messages.add_control_point(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, 44100),
            value=0.5))
        self.processor.handle_message(processor_messages.add_control_point(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(2048, 44100),
            value=1.0))
        self.processor.handle_message(processor_messages.remove_control_point(
            node_id='123',
            id=0x0002))

        self.process_block()
        self.assertBufferAllEqual('out', 0.5)
