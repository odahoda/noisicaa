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

import sys
import unittest

from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 import urid
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


cdef class TestProcessorPianoRollMixin(object):
    cdef PyHostData host_data
    cdef unique_ptr[Processor] processor_ptr
    cdef Processor* processor
    cdef PyBlockContext ctxt
    cdef uint8_t outbuf[10240]

    def setUp(self):
        self.host_data = PyHostData()
        self.host_data.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', self.host_data.ptr(), b'pianoroll')
        check(stor_processor)
        self.processor_ptr.reset(stor_processor.result())
        self.processor = self.processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'out', PortType.atomData, PortDirection.Output)
        check(self.processor.setup(spec.release()))

        self.ctxt = PyBlockContext()
        self.ctxt.block_size = 2 * 44100

        for s in range(self.ctxt.block_size):
            self.ctxt.append_sample_time(
                musical_time.PyMusicalTime(2 * s, 44100),
                musical_time.PyMusicalTime(2 * (s + 1), 44100))

        check(self.processor.connect_port(0, <BufferPtr>self.outbuf))

    def tearDown(self):
        if self.processor != NULL:
            self.processor.cleanup()
        self.processor_ptr.reset()

        self.host_data.cleanup()

    def get_output(self):
        seq = atom.Atom.wrap(urid.static_mapper, bytes(self.outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        return [(event.frames, [b for b in event.atom.data[0:3]]) for event in seq.events]

    def test_empty(self):
        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        seq = atom.Atom.wrap(urid.static_mapper, bytes(self.outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(self.get_output(), [])

    def test_add_interval(self):
        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0002,
                start_time=musical_time.PyMusicalTime(2, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=80,
                velocity=103))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        seq = atom.Atom.wrap(urid.static_mapper, bytes(self.outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(
            self.get_output(),
            [(5512, [144, 64, 100]),
             (11025, [144, 80, 103]),
             (16537, [128, 64, 0]),
             (16537, [128, 80, 0])])

    def test_remove_interval(self):
        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        check(self.processor.handle_message(msg.SerializeToString()))

        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_remove_interval=processor_message_pb2.ProcessorMessage.PianoRollRemoveInterval(
                id=0x0001))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        seq = atom.Atom.wrap(urid.static_mapper, bytes(self.outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(
            self.get_output(),
            [])

    def test_pianoroll_buffering(self):
        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        msg = processor_message_pb2.ProcessorMessage(
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0002,
                start_time=musical_time.PyMusicalTime(2, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=80,
                velocity=103))
        check(self.processor.handle_message(msg.SerializeToString()))

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        seq = atom.Atom.wrap(urid.static_mapper, bytes(self.outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(
            self.get_output(),
            [(5512, [144, 64, 100]),
             (11025, [144, 80, 103]),
             (16537, [128, 64, 0]),
             (16537, [128, 80, 0])])


class TestProcessorPianoRoll(TestProcessorPianoRollMixin, unittest.TestCase):
    pass
