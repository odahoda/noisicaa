#!/usr/bin/python3

import unittest

import numpy

from . import ladspa


class LadspaTest(unittest.TestCase):
    def test_foo(self):
        lib = ladspa.Library('/usr/lib/ladspa/sine.so')
        for desc in lib.descriptors:
            print(desc.id, desc.name, desc.label, desc.maker, desc.copyright)
            for port in desc.ports:
                print(port)


    def test_run_instance(self):
        lib = ladspa.Library('/usr/lib/ladspa/sine.so')
        desc = lib.get_descriptor('sine_fcac')
        inst = desc.instantiate(44100)
        try:
            p1 = numpy.ndarray(shape=(1,), dtype=numpy.float32)
            p1[0] = 440.0
            p2 = numpy.ndarray(shape=(1,), dtype=numpy.float32)
            p2[0] = 1.0
            p3 = numpy.ndarray(shape=(100,), dtype=numpy.float32)

            inst.connect_port(desc.ports[0], p1)
            inst.connect_port(desc.ports[1], p2)
            inst.connect_port(desc.ports[2], p3)

            inst.activate()
            inst.run(100)
            print(p3)
            inst.run(100)
            print(p3)

            inst.deactivate()
        finally:
            inst.close()
