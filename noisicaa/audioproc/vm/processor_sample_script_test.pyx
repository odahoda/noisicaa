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

import itertools
import math
import os.path
import sys
import unittest

from noisicaa import constants
from noisicaa.core.status cimport *
from . import musical_time
from . import processor
from . import processor_message_pb2
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *
from .time_mapper cimport PyTimeMapper
from .musical_time cimport *


TESTDATA = os.path.abspath(os.path.join(constants.ROOT, 'music', 'testdata'))


cdef class TestProcessorSampleScriptMixin(object):
    cdef PyHostData host_data
    cdef PyTimeMapper time_mapper
    cdef unique_ptr[Processor] processor_ptr
    cdef Processor* processor
    cdef PyBlockContext ctxt
    cdef float outlbuf[4096]
    cdef float outrbuf[4096]

    def setUp(self):
        self.host_data = PyHostData()
        self.host_data.setup()

        self.time_mapper = PyTimeMapper()
        self.time_mapper.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', self.host_data.ptr(), b'sample_script')
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

        check(self.processor.connect_port(0, <BufferPtr>self.outlbuf))
        check(self.processor.connect_port(1, <BufferPtr>self.outrbuf))

        self.sample1_path = os.path.join(TESTDATA, 'future-thunder1.wav')
        self.sample2_path = os.path.join(TESTDATA, 'kick-gettinglaid.wav')

    def tearDown(self):
        if self.processor != NULL:
            self.processor.cleanup()
        self.processor_ptr.reset()

        self.time_mapper.cleanup()
        self.host_data.cleanup()

    def get_output(self):
        return [float(v) for v in self.outlbuf[:self.ctxt.block_size]]

    def test_empty(self):
        check(self.processor.run(self.ctxt.get(), self.time_mapper.get()))

        self.assertTrue(all(v == 0.0 for v in self.get_output()))

    def test_single_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(2048, 44100).to_proto(),
                sample_path=self.sample1_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), self.time_mapper.get()))

        output = self.get_output()
        self.assertTrue(all(math.isclose(v, 0.0) for v in output[:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in output[2048:]))

    def test_two_samples(self):
        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                sample_path=self.sample1_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0002,
                time=musical_time.PyMusicalTime(3072, 44100).to_proto(),
                sample_path=self.sample2_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), self.time_mapper.get()))

        output = self.get_output()
        self.assertTrue(all(math.isclose(v, 0.0) for v in output[:1024]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in output[1024:]))

    def test_remove_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(2048, 44100).to_proto(),
                sample_path=self.sample1_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0002,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                sample_path=self.sample2_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            sample_script_remove_sample=processor_message_pb2.ProcessorMessage.SampleScriptRemoveSample(
                id=0x0002))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), self.time_mapper.get()))

        output = self.get_output()
        self.assertTrue(all(math.isclose(v, 0.0) for v in output[:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in output[2048:]))

    def test_seek_into_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(0, 1).to_proto(),
                sample_path=self.sample1_path))
        check(self.processor.handle_message(msg.SerializeToString()))

        self.ctxt.clear_time_map()
        it = self.time_mapper.find(musical_time.PyMusicalTime(1, 16))
        prev_mtime = next(it)
        for _ in range(self.ctxt.block_size):
            mtime = next(it)
            self.ctxt.append_sample_time(prev_mtime, mtime)
            prev_mtime = mtime

        check(self.processor.run(self.ctxt.get(), self.time_mapper.get()))

        output = self.get_output()
        self.assertTrue(any(not math.isclose(v, 0.0) for v in output))


class TestProcessorSampleScript(TestProcessorSampleScriptMixin, unittest.TestCase):
    pass
