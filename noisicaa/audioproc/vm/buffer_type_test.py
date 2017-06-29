#!/usr/bin/python3

import unittest

from noisicaa.bindings import lv2
from . import buffer_type

class BufferTypeTest(unittest.TestCase):

    def test_float(self):
        bt = buffer_type.Float()

        self.assertEqual(len(bt), 4)

    def test_float_array(self):
        bt = buffer_type.FloatArray(5)

        self.assertEqual(len(bt), 20)


class AtomDataTest(unittest.TestCase):
    def _fill_buffer(self, buf, data):
        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(buf, len(buf))

        urid = lv2.static_mapper.map(b'http://lv2plug.in/ns/ext/atom#String')
        with forge.sequence():
            for frames, item in data:
                forge.write_atom_event(frames, urid, item, len(item))

    def _read_buffer(self, buf):
        result = []

        seq = lv2.wrap_atom(lv2.static_mapper, buf)
        for event in seq.events:
            self.assertEqual(
                event.atom.type_uri, b'http://lv2plug.in/ns/ext/atom#String')
            result.append((event.frames, event.atom.data))

        return result

    def test_mix_buffers(self):
        bt = buffer_type.AtomData(1024)

        buf1 = bytearray(1024)
        self._fill_buffer(buf1, [(0, b'0'), (10, b'10'), (20, b'20'), (30, b'30')])

        buf2 = bytearray(1024)
        self._fill_buffer(buf2, [(1, b'1'), (9, b'9'), (11, b'11'), (15, b'15')])

        bt.mix_buffers(buf1, buf2)

        self.assertEqual(
            self._read_buffer(buf1),
            [(0, b'0'), (1, b'1'), (9, b'9'), (10, b'10'),
             (11, b'11'), (15, b'15'), (20, b'20'), (30, b'30')])

if __name__ == '__main__':
    unittest.main()
