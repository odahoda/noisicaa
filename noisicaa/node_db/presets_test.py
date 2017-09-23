#!/usr/bin/python3

import textwrap
import os.path
import unittest

from . import node_description
from . import presets
from .private import builtin_scanner

TESTDATA = os.path.join(os.path.dirname(__file__), 'testdata')


class PresetTest(unittest.TestCase):
    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()
