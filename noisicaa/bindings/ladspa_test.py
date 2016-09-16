#!/usr/bin/python3

import unittest

from . import ladspa


class LadspaTest(unittest.TestCase):
    def test_foo(self):
        lib = ladspa.Library('/usr/lib/ladspa/sine.so')
        for desc in lib.descriptors:
            print(desc.id, desc.name, desc.label, desc.maker, desc.copyright)
            for port in desc.ports:
                print(port)

