import unittest

from . import lv2
from . import sratom


class SratomTest(unittest.TestCase):
    def test_atom_to_turle(self):
        mapper = lv2.URID_Mapper()

        buf = bytearray(1024)

        forge = lv2.AtomForge(mapper)
        forge.set_buffer(buf, 1024)
        with forge.sequence():
            forge.write_midi_event(123, b'abc', 3)
            forge.write_midi_event(124, b'def', 3)

        turtle = sratom.atom_to_turtle(mapper, buf)
        self.assertIsInstance(turtle, str)

