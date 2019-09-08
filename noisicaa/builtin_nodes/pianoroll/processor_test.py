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

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa.audioproc.public import musical_time
from . import processor_messages
from . import processor_messages_pb2


class ProcessorPianoRollTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.host_system.set_block_size(2 * self.host_system.sample_rate)

        self.node_description = self.node_db['builtin://score-track']
        self.create_processor()

    def test_empty(self):
        self.process_block()
        self.assertMidiBufferIsEmpty('out')

    def test_add_interval(self):
        self.processor.handle_message(processor_messages.add_interval(
            node_id='123',
            id=0x0001,
            start_time=musical_time.PyMusicalTime(1, 4),
            end_time=musical_time.PyMusicalTime(3, 4),
            pitch=64,
            velocity=100))
        self.processor.handle_message(processor_messages.add_interval(
            node_id='123',
            id=0x0002,
            start_time=musical_time.PyMusicalTime(2, 4),
            end_time=musical_time.PyMusicalTime(3, 4),
            pitch=80,
            velocity=103))

        self.process_block()
        self.assertMidiBufferEqual(
            'out',
            [(11025, [144, 64, 100]),
             (22050, [144, 80, 103]),
             (33075, [128, 64, 0]),
             (33075, [128, 80, 0])])

    def test_remove_interval(self):
        self.processor.handle_message(processor_messages.add_interval(
            node_id='123',
            id=0x0001,
            start_time=musical_time.PyMusicalTime(1, 4),
            end_time=musical_time.PyMusicalTime(3, 4),
            pitch=64,
            velocity=100))
        self.processor.handle_message(processor_messages.remove_interval(
            node_id='123',
            id=0x0001))

        self.process_block()
        self.assertMidiBufferIsEmpty('out')

    def test_pianoroll_buffering(self):
        self.processor.handle_message(processor_messages.add_interval(
            node_id='123',
            id=0x0001,
            start_time=musical_time.PyMusicalTime(1, 4),
            end_time=musical_time.PyMusicalTime(3, 4),
            pitch=64,
            velocity=100))

        self.process_block()

        self.processor.handle_message(processor_messages.add_interval(
            node_id='123',
            id=0x0002,
            start_time=musical_time.PyMusicalTime(2, 4),
            end_time=musical_time.PyMusicalTime(3, 4),
            pitch=80,
            velocity=103))

        self.ctxt.sample_pos = 0
        self.process_block()
        self.assertMidiBufferEqual(
            'out',
            [(11025, [144, 64, 100]),
             (22050, [144, 80, 103]),
             (33075, [128, 64, 0]),
             (33075, [128, 80, 0])])

    def test_segments(self):
        self.processor.handle_message(processor_messages.add_segment(
            node_id='123',
            segment_id=0x0001,
            duration=musical_time.PyMusicalDuration(1, 4)))
        self.processor.handle_message(processor_messages.add_segment_ref(
            node_id='123',
            segment_ref_id=0x0002,
            time=musical_time.PyMusicalTime(0, 4),
            segment_id=0x0001))
        self.processor.handle_message(processor_messages.add_event(
            node_id='123',
            segment_id=0x0001,
            event_id=0x0003,
            time=musical_time.PyMusicalTime(2, 16),
            type=processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_ON,
            channel=0,
            pitch=64,
            velocity=100))
        self.processor.handle_message(processor_messages.add_event(
            node_id='123',
            segment_id=0x0001,
            event_id=0x0004,
            time=musical_time.PyMusicalTime(3, 16),
            type=processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_OFF,
            channel=0,
            pitch=64,
            velocity=0))

        self.processor.handle_message(processor_messages.add_segment(
            node_id='123',
            segment_id=0x0005,
            duration=musical_time.PyMusicalDuration(1, 4)))
        self.processor.handle_message(processor_messages.add_segment_ref(
            node_id='123',
            segment_ref_id=0x0006,
            time=musical_time.PyMusicalTime(2, 4),
            segment_id=0x0005))
        self.processor.handle_message(processor_messages.add_event(
            node_id='123',
            segment_id=0x0005,
            event_id=0x0007,
            time=musical_time.PyMusicalTime(2, 16),
            type=processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_ON,
            channel=0,
            pitch=63,
            velocity=110))
        self.processor.handle_message(processor_messages.add_event(
            node_id='123',
            segment_id=0x0005,
            event_id=0x0007,
            time=musical_time.PyMusicalTime(3, 16),
            type=processor_messages_pb2.PianoRollMutation.AddEvent.NOTE_OFF,
            channel=0,
            pitch=63,
            velocity=0))

        self.process_block()
        self.assertMidiBufferEqual(
            'out',
            [(5512, [0x90, 64, 100]),
             (8268, [0x80, 64, 0]),
             (27562, [0x90, 63, 110]),
             (30318, [0x80, 63, 0]),
            ])

        self.processor.handle_message(processor_messages.remove_event(
            node_id='123',
            segment_id=0x0005,
            event_id=0x0007))
        self.processor.handle_message(processor_messages.remove_event(
            node_id='123',
            segment_id=0x0005,
            event_id=0x0008))

        self.ctxt.sample_pos = 0
        self.process_block()
        self.assertMidiBufferEqual(
            'out',
            [(5512, [0x90, 64, 100]),
             (8268, [0x80, 64, 0]),
            ])

        self.processor.handle_message(processor_messages.remove_segment_ref(
            node_id='123',
            segment_ref_id=0x0006))
        self.processor.handle_message(processor_messages.remove_segment(
            node_id='123',
            segment_id=0x0005))

        self.ctxt.sample_pos = 0
        self.process_block()
        self.assertMidiBufferEqual(
            'out',
            [(5512, [0x90, 64, 100]),
             (8268, [0x80, 64, 0]),
            ])
