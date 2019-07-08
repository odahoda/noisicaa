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


class ProcessorCsoundTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def test_csound(self):
        self.node_description = node_db.NodeDescription(
            uri='test://test',
            type=node_db.NodeDescription.PROCESSOR,
            ports=[
                node_db.PortDescription(
                    name='gain',
                    direction=node_db.PortDescription.INPUT,
                    types=[node_db.PortDescription.KRATE_CONTROL],
                ),
                node_db.PortDescription(
                    name='in',
                    direction=node_db.PortDescription.INPUT,
                    types=[node_db.PortDescription.AUDIO],
                ),
                node_db.PortDescription(
                    name='out',
                    direction=node_db.PortDescription.OUTPUT,
                    types=[node_db.PortDescription.AUDIO],
                ),
            ],
            processor=node_db.ProcessorDescription(
                type='builtin://csound',
            ),
            csound=node_db.CSoundDescription(
                orchestra=textwrap.dedent("""\
                    sr=44100
                    0dbfs=1
                    ksmps=32
                    nchnls=1

                    gkGain chnexport "gain", 1
                    gaIn chnexport "in", 1
                    gaOut chnexport "out", 2

                    instr 1
                      gaOut = gkGain * gaIn
                    endin
                """),
                score='i1 0 -1',
            ),
        )
        self.create_processor()
        self.fill_buffer('in', 1.0)
        self.fill_buffer('gain', 0.5)

        self.process_block()
        self.assertBufferAllEqual('out', 0.5)

    def test_event_input_port(self):
        self.node_description = node_db.NodeDescription(
            uri='test://test',
            type=node_db.NodeDescription.PROCESSOR,
            ports=[
                node_db.PortDescription(
                    name='in',
                    direction=node_db.PortDescription.INPUT,
                    types=[node_db.PortDescription.EVENTS],
                ),
                node_db.PortDescription(
                    name='out',
                    direction=node_db.PortDescription.OUTPUT,
                    types=[node_db.PortDescription.AUDIO],
                ),
            ],
            processor=node_db.ProcessorDescription(
                type='builtin://csound',
            ),
            csound=node_db.CSoundDescription(
                orchestra=textwrap.dedent("""\
                    sr=44100
                    0dbfs=1
                    ksmps=32
                    nchnls=1

                    gaOut chnexport "out", 2

                    instr 1
                      iPitch = p4
                      iVelocity = p5

                      iFreq = cpsmidinn(iPitch)
                      iVolume = -20 * log10(127^2 / iVelocity^2)

                      gaOut = db(iVolume) * linseg(0, 0.08, 1, 0.1, 0.6, 0.5, 0.0) * poscil(1.0, iFreq)
                    endin
                """),
                score='',
            ),
        )
        self.create_processor()
        self.fill_midi_buffer(
            'in',
            [(0, [0x90, 60, 100]),
             (64, [0x80, 60, 0])])

        self.process_block()
        self.assertBufferIsNotQuiet('out')
