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
import os
import os.path

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa.audioproc.public import musical_time
from . import processor_messages


class ProcessorSampleScriptTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.sample1_path = os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')
        self.sample2_path = os.path.join(unittest.TESTDATA_DIR, 'kick-gettinglaid.wav')

        self.host_system.set_block_size(4096)

        self.node_description = self.node_db['builtin://sample-track']
        self.create_processor()

    def test_empty(self):
        self.process_block()
        self.assertBufferIsQuiet('out:left')
        self.assertBufferIsQuiet('out:right')

    def test_single_sample(self):
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(2048, 44100),
            sample_path=self.sample1_path))

        self.process_block()
        self.assertTrue(all(math.isclose(v, 0.0) for v in self.buffers['out:left'][:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.buffers['out:left'][2048:]))

    def test_two_samples(self):
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(1024, 44100),
            sample_path=self.sample1_path))
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(3072, 44100),
            sample_path=self.sample2_path))

        self.process_block()
        self.assertTrue(all(math.isclose(v, 0.0) for v in self.buffers['out:left'][:1024]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.buffers['out:left'][1024:]))

    def test_remove_sample(self):
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(2048, 44100),
            sample_path=self.sample1_path))
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0002,
            time=musical_time.PyMusicalTime(1024, 44100),
            sample_path=self.sample2_path))
        self.processor.handle_message(processor_messages.remove_sample(
            node_id='123',
            id=0x0002))

        self.process_block()

        self.assertTrue(all(math.isclose(v, 0.0) for v in self.buffers['out:left'][:2048]))
        self.assertTrue(any(not math.isclose(v, 0.0) for v in self.buffers['out:left'][2048:]))

    def test_seek_into_sample(self):
        self.processor.handle_message(processor_messages.add_sample(
            node_id='123',
            id=0x0001,
            time=musical_time.PyMusicalTime(0, 1),
            sample_path=self.sample1_path))

        self.ctxt.clear_time_map(self.host_system.block_size)
        it = self.time_mapper.find(musical_time.PyMusicalTime(1, 16))
        prev_mtime = next(it)
        for s in range(self.host_system.block_size):
            mtime = next(it)
            self.ctxt.set_sample_time(s, prev_mtime, mtime)
            prev_mtime = mtime

        self.process_block()
        self.assertBufferIsNotQuiet('out:left')
