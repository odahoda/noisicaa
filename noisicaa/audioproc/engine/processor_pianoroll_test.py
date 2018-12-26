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

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa.bindings.lv2 import atom
from noisicaa.bindings.lv2 import urid
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import processor_message_pb2
from . import block_context
from . import buffers
from . import processor


class ProcessorPianoRollTestMixin(
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
        self.host_system.set_block_size(2 * 44100)

        plugin_uri = 'builtin://score_track'
        node_description = self.node_db[plugin_uri]

        self.proc = processor.PyProcessor('test_node', self.host_system, node_description)
        self.proc.setup()

        self.buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        self.outbuf = self.buffer_mgr.allocate('out', buffers.PyAtomDataBuffer())

        self.ctxt = block_context.PyBlockContext()

        self.ctxt.clear_time_map(self.host_system.block_size)
        for s in range(self.host_system.block_size):
            self.ctxt.set_sample_time(
                s,
                musical_time.PyMusicalTime(2 * s, 44100),
                musical_time.PyMusicalTime(2 * (s + 1), 44100))

        self.proc.connect_port(self.ctxt, 0, self.buffer_mgr.data('out'))

    def cleanup_testcase(self):
        if self.proc is not None:
            self.proc.cleanup()

    def get_output(self):
        seq = atom.wrap_atom(urid.static_mapper, self.outbuf)
        self.assertIsInstance(seq, atom.Sequence)
        return [(event.frames, [b for b in event.atom.data[0:3]]) for event in seq.events]

    def test_empty(self):
        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper
        self.assertEqual(self.get_output(), [])

    def test_add_interval(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        self.proc.handle_message(msg)

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0002,
                start_time=musical_time.PyMusicalTime(2, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=80,
                velocity=103))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertEqual(
            self.get_output(),
            [(5512, [144, 64, 100]),
             (11025, [144, 80, 103]),
             (16537, [128, 64, 0]),
             (16537, [128, 80, 0])])

    def test_remove_interval(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        self.proc.handle_message(msg)

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_remove_interval=(
                processor_message_pb2.ProcessorMessage.PianoRollRemoveInterval(
                    id=0x0001)))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertEqual(
            self.get_output(),
            [])

    def test_pianoroll_buffering(self):
        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0001,
                start_time=musical_time.PyMusicalTime(1, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=64,
                velocity=100))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        msg = processor_message_pb2.ProcessorMessage(
            node_id='123',
            pianoroll_add_interval=processor_message_pb2.ProcessorMessage.PianoRollAddInterval(
                id=0x0002,
                start_time=musical_time.PyMusicalTime(2, 4).to_proto(),
                end_time=musical_time.PyMusicalTime(3, 4).to_proto(),
                pitch=80,
                velocity=103))
        self.proc.handle_message(msg)

        self.proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        self.assertEqual(
            self.get_output(),
            [(5512, [144, 64, 100]),
             (11025, [144, 80, 103]),
             (16537, [128, 64, 0]),
             (16537, [128, 80, 0])])
