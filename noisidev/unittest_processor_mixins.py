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

from . import unittest_mixins
from . import unittest_engine_mixins
from . import unittest_engine_utils
from noisicaa import lv2
from noisicaa import node_db
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import time_mapper
from noisicaa.audioproc.engine import processor
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import buffer_arena


class ProcessorTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.node_description = None  # type: node_db.NodeDescription
        self.processor = None  # type: processor.PyProcessor
        self.time_mapper = None  # type: time_mapper.PyTimeMapper
        self.arena = None  # type: buffer_arena.PyBufferArena
        self.buffers = None  # type: unittest_engine_utils.BufferManager
        self.__buffers = None  # type: List[buffers.PyBuffer]
        self.ctxt = None  # type: block_context.PyBlockContext

    def setup_testcase(self):
        self.arena = buffer_arena.PyBufferArena(2**20)
        self.buffers = unittest_engine_utils.BufferManager(self.host_system, self.arena)

        self.ctxt = block_context.PyBlockContext(buffer_arena=self.arena)
        self.ctxt.sample_pos = 0

        self.time_mapper = time_mapper.PyTimeMapper(self.host_system.sample_rate)
        self.time_mapper.setup()

    def cleanup_testcase(self):
        if self.processor is not None:
            self.processor.cleanup()
            self.processor = None

        if self.time_mapper is not None:
            self.time_mapper.cleanup()

        self.buffers = None
        self.ctxt = None
        self.arena = None

    def port_desc(self, name):
        for port_desc in self.node_description.ports:
            if port_desc.name == name:
                return port_desc
        raise ValueError(name)

    def fill_buffer(self, name, value):
        buf = self.buffers[name]
        if isinstance(self.buffers.type(name), buffers.PyFloatAudioBlockBuffer):
            for i in range(self.host_system.block_size):
                buf[i] = value
        elif isinstance(self.buffers.type(name), buffers.PyFloatControlValueBuffer):
            buf[0] = value
        else:
            raise ValueError("%s: %s" % (name, self.buffers[name].type))

    def fill_midi_buffer(self, name, events):
        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(self.buffers.data(name), 10240)
        with forge.sequence():
            for tpos, midi in events:
                assert 0 <= tpos < self.host_system.block_size
                forge.write_midi_event(tpos, bytes(midi), len(midi))

    def clear_buffer(self, name):
        if isinstance(self.buffers.type(name), buffers.PyAtomDataBuffer):
            forge = lv2.AtomForge(self.urid_mapper)
            forge.set_buffer(self.buffers.data(name), 10240)
            with forge.sequence():
                pass
        else:
            self.fill_buffer(name, 0.0)

    def clear_buffers(self):
        for port_desc in self.node_description.ports:
            self.clear_buffer(port_desc.name)

    def assertBufferAllEqual(self, name, should_value):
        for idx, is_value in enumerate(self.buffers[name]):
            self.assertAlmostEqual(
                is_value, should_value,
                msg='%s != %s @ idx=%d' % (is_value, should_value, idx))

    def assertBufferRangeEqual(self, name, first, last, should_value):
        for idx, is_value in enumerate(self.buffers[name][first:last], first):
            self.assertAlmostEqual(
                is_value, should_value,
                msg='%s != %s @ idx=%d' % (is_value, should_value, idx))

    def assertBufferIsQuiet(self, name):
        buf = self.buffers[name]
        self.assertTrue(any(v == 0.0 for v in buf))

    def assertBufferIsNotQuiet(self, name):
        buf = self.buffers[name]
        self.assertTrue(any(v != 0.0 for v in buf))

    def assertMidiBufferIsEmpty(self, name):
        seq = lv2.wrap_atom(lv2.DynamicURIDMapper(), self.buffers[name])
        self.assertEqual(seq.type_uri, 'http://lv2plug.in/ns/ext/atom#Sequence')
        self.assertEqual(len(list(seq.sequence)), 0)

    def assertMidiBufferEqual(self, name, should_events):
        seq = lv2.wrap_atom(lv2.DynamicURIDMapper(), self.buffers[name])
        self.assertEqual(seq.type_uri, 'http://lv2plug.in/ns/ext/atom#Sequence')
        is_events = [
            (event.frames, [b for b in event.atom.data[0:3]])
            for event in seq.sequence]
        self.assertEqual(is_events, should_events)

    def create_processor(self):
        self.processor = processor.PyProcessor('realm', 'test_node', self.host_system, self.node_description)
        self.processor.setup()

        self.buffers.allocate_from_node_description(self.node_description)
        self.clear_buffers()

        self.__buffers = []
        for port_idx, port_desc in enumerate(self.node_description.ports):
            buf = buffers.PyBuffer(
                self.host_system, self.buffers.type(port_desc.name), self.buffers.data(port_desc.name))
            self.__buffers.append(buf)
            self.processor.connect_port(self.ctxt, port_idx, buf)

    def process_block(self):
        self.ctxt.clear_time_map(self.host_system.block_size)
        for s in range(self.host_system.block_size):
            self.ctxt.set_sample_time(
                s,
                musical_time.PyMusicalTime(self.ctxt.sample_pos + s, self.host_system.sample_rate),
                musical_time.PyMusicalTime(self.ctxt.sample_pos + s + 1, self.host_system.sample_rate))

        self.processor.process_block(self.ctxt, self.time_mapper)

        self.ctxt.sample_pos += self.host_system.block_size
