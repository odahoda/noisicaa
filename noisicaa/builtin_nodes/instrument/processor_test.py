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

import os
import os.path

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa.audioproc.public import instrument_spec_pb2
from . import processor_messages


class ProcessorInstrumentTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):

    def playback_test(self, instrument_spec):
        self.node_description = self.node_db['builtin://instrument']
        self.create_processor()

        self.processor.handle_message(processor_messages.change_instrument(
            'test_node', instrument_spec))

        # run once empty to give csound some chance to initialize the ftable
        self.process_block()

        self.fill_midi_buffer(
            'in',
            [(0, [0x90, 60, 100]),
             (64, [0x80, 60, 0])])
        self.clear_buffer('out:left')
        self.clear_buffer('out:right')

        self.process_block()
        self.assertBufferIsNotQuiet('out:left')
        self.assertBufferIsNotQuiet('out:right')

    def test_sample(self):
        self.playback_test(
            instrument_spec_pb2.InstrumentSpec(
                sample=instrument_spec_pb2.SampleInstrumentSpec(
                    path=os.path.join(unittest.TESTDATA_DIR, 'snare.wav'))))

    def test_sf2(self):
        self.playback_test(
            instrument_spec_pb2.InstrumentSpec(
                sf2=instrument_spec_pb2.SF2InstrumentSpec(
                    path=os.path.join(unittest.TESTDATA_DIR, 'sf2test.sf2'),
                    bank=0,
                    preset=0)))
