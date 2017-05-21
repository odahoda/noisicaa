import unittest

from noisicaa.bindings import sratom
from . import atom
from . import urid


class AtomForgeTest(unittest.TestCase):
    def test_forge(self):
        buf = bytearray(1024)

        mapper = urid.URID_StaticMapper()

        forge = atom.AtomForge(mapper)
        forge.set_buffer(buf, 1024)

        with forge.sequence():
            forge.write_midi_event(0, b'abc', 3)
            forge.write_midi_event(1, b'abc', 3)

        print(sratom.atom_to_turtle(mapper, buf))
