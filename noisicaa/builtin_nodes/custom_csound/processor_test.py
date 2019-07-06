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

import textwrap

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa import node_db
from noisicaa.audioproc.public import node_parameters_pb2
from . import processor_pb2


class ProcessorCustomCSoundTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.node_description = self.node_db['builtin://custom-csound']
        self.node_description.ports.add(
            name='in',
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.INPUT)
        self.node_description.ports.add(
            name='out',
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.OUTPUT)
        self.node_description.ports.add(
            name='ctrl',
            type=node_db.PortDescription.KRATE_CONTROL,
            direction=node_db.PortDescription.INPUT)
        self.node_description.ports.add(
            name='ev',
            type=node_db.PortDescription.EVENTS,
            direction=node_db.PortDescription.INPUT)

        self.create_processor()

    def set_code(self, orchestra, score):
        params = node_parameters_pb2.NodeParameters()
        csound_params = params.Extensions[processor_pb2.custom_csound_parameters]
        csound_params.orchestra = orchestra
        csound_params.score = score
        self.processor.set_parameters(params)

    def test_synth(self):
        orchestra = textwrap.dedent('''\
            0dbfs = 1.0
            ksmps = 32
            nchnls = 2

            gaIn chnexport "in", 1
            gaOut chnexport "out", 2
            gkCtrl chnexport "ctrl", 1

            instr 1
              gaOut = 1.0
            endin
            ''')
        score = textwrap.dedent('''\
            e 10000
            ''')
        self.set_code(orchestra, score)

        self.fill_midi_buffer(
            'ev',
            [(0, [0x90, 60, 100]),
             (64, [0x80, 60, 0])])

        self.process_block()

        # The instrument only gets active with one cycle delay, so the first 32 samples a silence.
        # Turning it off though works instantaneously.
        audio_out = self.buffers['out']
        self.assertTrue(all(v == 0.0 for v in audio_out[:32]))
        self.assertTrue(all(v == 1.0 for v in audio_out[32:64]))
        self.assertTrue(all(v == 0.0 for v in audio_out[64:]))

    def test_filter(self):
        orchestra = textwrap.dedent('''\
            0dbfs = 1.0
            ksmps = 32
            nchnls = 2

            gaIn chnexport "in", 1
            gaOut chnexport "out", 2
            gkCtrl chnexport "ctrl", 1

            instr 1
              gaOut = gkCtrl * gaIn
            endin
            ''')
        score = textwrap.dedent('''\
            i1 0 -1
            e 10000
            ''')
        self.set_code(orchestra, score)

        self.fill_buffer('in', 1.0)
        self.fill_buffer('ctrl', 0.5)

        self.process_block()

        # The instrument only gets active with one cycle delay, so the first 32 samples a silence.
        audio_out = self.buffers['out']
        self.assertTrue(all(v == 0.0 for v in audio_out[:32]))
        self.assertTrue(all(v == 0.5 for v in audio_out[32:]))
