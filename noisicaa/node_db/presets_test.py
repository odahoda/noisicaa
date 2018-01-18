#!/usr/bin/python3

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

import textwrap
import os.path

from noisidev import unittest
from . import node_description
from . import presets
from .private import builtin_scanner

TESTDATA = os.path.join(os.path.dirname(__file__), 'testdata')


class PresetTest(unittest.TestCase):
    def setup_testcase(self):
        scanner = builtin_scanner.BuiltinScanner()
        self.nodes = dict(scanner.scan())
        self.node_factory = self.nodes.get

    def test_load(self):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <preset>
              <display-name>Light Reverb</display-name>
              <node uri="builtin://custom_csound"/>
              <parameter-values>
                <parameter name="orchestra"><![CDATA[
            instr 1
              gaOutL, gaOutR reverbsc gaInL, gaInR, 0.2, 2000
            endin
            ]]></parameter>
                <parameter name="score"><![CDATA[
            i1 0 -1
            ]]></parameter>
              </parameter-values>
            </preset>
            """)

        preset = presets.Preset.from_string(xml, self.node_factory)
        self.assertEqual(preset.display_name, "Light Reverb")
        self.assertEqual(preset.node_uri, 'builtin://custom_csound')
        self.assertIsInstance(preset.node_description, node_description.NodeDescription)
        self.assertEqual(preset.node_description.node_cls, 'processor')
