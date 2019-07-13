#!/usr/bin/python3

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

import builtins
import textwrap

from mox3 import stubout
from pyfakefs import fake_filesystem

from noisidev import unittest
from . import node_description_pb2
from . import faust_parser


class FauseJsonToNodeDescriptionTest(unittest.TestCase):
    def setup_testcase(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_foo(self):
        processor_json = textwrap.dedent('''\
            {
              "name": "Oscillator",
              "filename": "processor",
              "inputs": "1",
              "outputs": "1",
              "meta": [
                { "basics.lib/name": "Faust Basic Element Library" },
                { "basics.lib/version": "0.0" },
                { "filename": "processor" },
                { "input0_display_name": "Frequency (Hz)" },
                { "input0_name": "freq" },
                { "input0_float_value": "1 20000 440" },
                { "input0_scale": "log" },
                { "input0_type": "ARATE_CONTROL" },
                { "maths.lib/author": "GRAME" },
                { "maths.lib/copyright": "GRAME" },
                { "maths.lib/license": "LGPL with exception" },
                { "maths.lib/name": "Faust Math Library" },
                { "maths.lib/version": "2.1" },
                { "name": "Oscillator" },
                { "oscillators.lib/name": "Faust Oscillator Library" },
                { "oscillators.lib/version": "0.0" },
                { "output0_display_name": "Output" },
                { "output0_name": "out" },
                { "output0_type": "AUDIO" },
                { "uri": "builtin://oscillator" }
              ],
              "ui": [
                {
                  "type": "vgroup",
                  "label": "Oscillator",
                  "items": [
                    {
                      "type": "nentry",
                      "label": "waveform",
                      "address": "/Oscillator/waveform",
                      "meta": [
                        { "display_name": "Waveform" },
                        { "style": "menu{'Sine':0.0; 'Sawtooth':1.0; 'Square':2.0}" }
                      ],
                      "init": "0",
                      "min": "0",
                      "max": "2",
                      "step": "1"
                    }
                  ]
                }
              ]
            }
            ''')
        self.fs.create_file('/processor.json', contents=processor_json)

        node_desc = faust_parser.faust_json_to_node_description('/processor.json')
        self.assertEqual(node_desc.display_name, 'Oscillator')
        self.assertEqual(node_desc.uri, 'builtin://oscillator')
        ports = {
            port_desc.name: port_desc
            for port_desc in node_desc.ports
        }
        self.assertEqual(set(ports), {'waveform', 'out', 'freq'})
        self.assertEqual(ports['out'].display_name, "Output")
        self.assertEqual(ports['out'].types, [node_description_pb2.PortDescription.AUDIO])
        self.assertEqual(ports['out'].direction, node_description_pb2.PortDescription.OUTPUT)
        self.assertEqual(ports['freq'].display_name, "Frequency (Hz)")
        self.assertEqual(ports['freq'].types, [node_description_pb2.PortDescription.ARATE_CONTROL])
        self.assertEqual(ports['freq'].direction, node_description_pb2.PortDescription.INPUT)
        self.assertEqual(ports['freq'].float_value.min, 1.0)
        self.assertEqual(ports['freq'].float_value.max, 20000.0)
        self.assertEqual(ports['freq'].float_value.default, 440.0)
        self.assertEqual(
            ports['freq'].float_value.scale, node_description_pb2.FloatValueDescription.LOG)
        self.assertEqual(ports['waveform'].display_name, "Waveform")
        self.assertEqual(ports['waveform'].types,
                         [node_description_pb2.PortDescription.KRATE_CONTROL])
        self.assertEqual(ports['waveform'].direction, node_description_pb2.PortDescription.INPUT)
        self.assertEqual(ports['waveform'].enum_value.default, 0.0)
        self.assertEqual(ports['waveform'].enum_value.items[0].name, 'Sine')
        self.assertEqual(ports['waveform'].enum_value.items[0].value, 0.0)
        self.assertEqual(ports['waveform'].enum_value.items[1].name, 'Sawtooth')
        self.assertEqual(ports['waveform'].enum_value.items[1].value, 1.0)
        self.assertEqual(ports['waveform'].enum_value.items[2].name, 'Square')
        self.assertEqual(ports['waveform'].enum_value.items[2].value, 2.0)
