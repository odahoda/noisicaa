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
import os
import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import processor_message_pb2
from noisicaa.audioproc.public import time_mapper
from . import block_context
from . import buffers
from . import processor


class ProcessorSampleScriptTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.proc = None
        self.arena = None
        self.buffer_mgr = None
        self.time_mapper = None
        self.ctxt = None
        self.outrbuf = None
        self.outlbuf = None

        self.sample1_path = os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')
        self.sample2_path = os.path.join(unittest.TESTDATA_DIR, 'kick-gettinglaid.wav')

    def setup_testcase(self):
        self.host_system.set_block_size(4096)

        plugin_uri = 'builtin://sample_script'
        node_description = self.node_db[plugin_uri]

        self.proc = processor.PyProcessor('test_node', self.host_system, node_description)
        self.proc.setup()

        self.buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        self.outlbuf = self.buffer_mgr.allocate('out:left', buffers.PyFloatAudioBlockBuffer())
        self.outrbuf = self.buffer_mgr.allocate('out:right', buffers.PyFloatAudioBlockBuffer())

        self.time_mapper = time_mapper.PyTimeMapper(self.host_system.sample_rate)
        self.time_mapper.setup()

        self.ctxt = block_context.PyBlockContext()

        for s in range(self.host_system.block_size):
            self.ctxt.append_sample_time(
                musical_time.PyMusicalTime(s, 44100),
                musical_time.PyMusicalTime(s + 1, 44100))

        self.proc.connect_port(self.ctxt, 0, self.buffer_mgr.data('out:left'))
        self.proc.connect_port(self.ctxt, 1, self.buffer_mgr.data('out:right'))

    def cleanup_testcase(self):
        if self.time_mapper is not None:
            self.time_mapper.cleanup()
            self.time_mapper = None

        if self.proc is not None:
            self.proc.cleanup()
            self.proc = None

    def test_empty(self):
        self.proc.process_block(self.ctxt, self.time_mapper)

        self.assertTrue(all(v == 0.0 for v in self.outlbuf))

    def test_single_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(2048, 44100).to_proto(),
                sample_path=self.sample1_path))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, self.time_mapper)

        self.assertTrue(all(math.isclose(v, 0.0) for v in self.outlbuf[:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.outlbuf[2048:]))

    def test_two_samples(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                sample_path=self.sample1_path))
        self.proc.handle_message(msg)

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0002,
                time=musical_time.PyMusicalTime(3072, 44100).to_proto(),
                sample_path=self.sample2_path))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, self.time_mapper)

        self.assertTrue(all(math.isclose(v, 0.0) for v in self.outlbuf[:1024]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.outlbuf[1024:]))

    def test_remove_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(2048, 44100).to_proto(),
                sample_path=self.sample1_path))
        self.proc.handle_message(msg)

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0002,
                time=musical_time.PyMusicalTime(1024, 44100).to_proto(),
                sample_path=self.sample2_path))
        self.proc.handle_message(msg)

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_remove_sample=(
                processor_message_pb2.ProcessorMessage.SampleScriptRemoveSample(
                    id=0x0002)))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, self.time_mapper)

        self.assertTrue(all(math.isclose(v, 0.0) for v in self.outlbuf[:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.outlbuf[2048:]))

    def test_seek_into_sample(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            sample_script_add_sample=processor_message_pb2.ProcessorMessage.SampleScriptAddSample(
                id=0x0001,
                time=musical_time.PyMusicalTime(0, 1).to_proto(),
                sample_path=self.sample1_path))
        self.proc.handle_message(msg)

        self.ctxt.clear_time_map()
        it = self.time_mapper.find(musical_time.PyMusicalTime(1, 16))
        prev_mtime = next(it)
        for _ in range(self.host_system.block_size):
            mtime = next(it)
            self.ctxt.append_sample_time(prev_mtime, mtime)
            prev_mtime = mtime

        self.proc.process_block(self.ctxt, self.time_mapper)

        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.outlbuf))
