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
from noisicaa import lv2
from . import processor_messages


class ProcessorMidiSourceTes(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):

    def setup_testcase(self):
        self.input_events = bytearray(10240)
        self.ctxt.set_input_events(self.input_events)

        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(self.input_events, 10240)
        with forge.sequence():
            forge.write_frame_time(0)
            with forge.tuple():
                forge.write_string('test://device1')
                forge.write_midi_atom(bytes([0x90, 60, 100]), 3)

            forge.write_frame_time(64)
            with forge.tuple():
                forge.write_string('test://device1')
                forge.write_midi_atom(bytes([0x80, 60, 0]), 3)

            forge.write_frame_time(64)
            with forge.tuple():
                forge.write_string('test://device2')
                forge.write_midi_atom(bytes([0x90, 60, 80]), 3)

            forge.write_frame_time(80)
            with forge.tuple():
                forge.write_string('test://device2')
                forge.write_midi_atom(bytes([0x91, 60, 80]), 3)

        self.node_description = self.node_db['builtin://midi-source']
        self.create_processor()

    def get_output(self):
        seq = lv2.wrap_atom(self.urid_mapper, self.buffers['out'])
        self.assertEqual(seq.type_uri, 'http://lv2plug.in/ns/ext/atom#Sequence')
        return [(event.frames, [b for b in event.atom.data[0:3]]) for event in seq.sequence]

    def test_match_device1(self):
        self.processor.handle_message(
            processor_messages.update('test_node', channel_filter=-1, device_uri='test://device1'))

        self.process_block()
        self.assertEqual(
            self.get_output(),
            [(0, [0x90, 60, 100]),
             (64, [0x80, 60, 0])])

    def test_match_device2_channel1(self):
        self.processor.handle_message(
            processor_messages.update('test_node', channel_filter=1, device_uri='test://device2'))

        self.process_block()
        self.assertEqual(
            self.get_output(),
            [(80, [0x91, 60, 80])])

    def test_match_device2_all_channel(self):
        self.processor.handle_message(
            processor_messages.update('test_node', channel_filter=-1, device_uri='test://device2'))

        self.process_block()
        self.assertEqual(
            self.get_output(),
            [(64, [0x90, 60, 80]),
             (80, [0x91, 60, 80])])

    def test_client_message(self):
        self.processor.handle_message(
            processor_messages.update('test_node', channel_filter=-1, device_uri='null://'))
        self.processor.handle_message(
            processor_messages.note_on_event('test_node', channel=1, note=53, velocity=70))

        self.process_block()
        self.assertEqual(
            self.get_output(),
            [(0, [0x91, 53, 70])])
