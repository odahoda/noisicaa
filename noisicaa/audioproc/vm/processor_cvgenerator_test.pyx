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

from libc.stdint cimport uint8_t
from libcpp.memory cimport unique_ptr

import math
import sys
import unittest

from noisicaa.core.status cimport *
from . import musical_time
from . import processor
from . import processor_message_pb2
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *
from .musical_time cimport *


cdef class TestProcessorCVGeneratorMixin(object):
    cdef PyHostData host_data
    cdef unique_ptr[Processor] processor_ptr
    cdef Processor* processor
    cdef PyBlockContext ctxt
    cdef float outbuf[4096]

    def setUp(self):
        self.host_data = PyHostData()
        self.host_data.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', self.host_data.ptr(), b'cvgenerator')
        check(stor_processor)
        self.processor_ptr.reset(stor_processor.result())
        self.processor = self.processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'out', PortType.aRateControl, PortDirection.Output)
        check(self.processor.setup(spec.release()))

        self.ctxt = PyBlockContext()
        self.ctxt.block_size = 4096

        for s in range(self.ctxt.block_size):
            self.ctxt.append_sample_time(
                musical_time.PyMusicalTime(s, 44100),
                musical_time.PyMusicalTime((s + 1), 44100))

        check(self.processor.connect_port(0, <BufferPtr>self.outbuf))

    def tearDown(self):
        if self.processor != NULL:
            self.processor.cleanup()
        self.processor_ptr.reset()

        self.host_data.cleanup()

    def get_output(self):
        return [float(v) for v in self.outbuf[:self.ctxt.block_size]]

    def test_empty(self):
        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        self.assertTrue(all(v == 0.0 for v in self.get_output()))

    def test_single_control_point(self):
        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_add_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorAddControlPoint(
                id=0x0001,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                value=0.5))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        self.assertTrue(all(math.isclose(v, 0.5) for v in self.get_output()))

    def test_two_control_points(self):
        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_add_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorAddControlPoint(
                id=0x0001,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                value=0.2))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_add_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorAddControlPoint(
                id=0x0002,
                time=musical_time.PyMusicalTime(3072, 44100).to_proto(),
                value=0.8))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        output = self.get_output()

        # Constant value before first control point.
        self.assertTrue(all(math.isclose(v, 0.2, rel_tol=0.001) for v in output[:1024]))

        # Linear ramp up between first and second control points.
        self.assertTrue(all(math.isclose(v, e, rel_tol=0.001)
                            for v, e
                            in zip(output[1024:3072],
                                   [0.2 + 0.6 * i / 2048 for i in range(2048)])))

        # Constant value after second control point.
        self.assertTrue(all(math.isclose(v, 0.8, rel_tol=0.001) for v in output[3072:]))

    def test_remove_control_point(self):
        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_add_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorAddControlPoint(
                id=0x0001,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                value=0.5))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_add_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorAddControlPoint(
                id=0x0002,
                time=musical_time.PyMusicalTime(2048, 44100).to_proto(),
                value=1.0))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            cvgenerator_remove_control_point=processor_message_pb2.ProcessorMessage.CVGeneratorRemoveControlPoint(
                id=0x0002))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        self.assertTrue(all(math.isclose(v, 0.5) for v in self.get_output()))


class TestProcessorCVGenerator(TestProcessorCVGeneratorMixin, unittest.TestCase):
    pass
