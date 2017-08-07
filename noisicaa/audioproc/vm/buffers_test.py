#!/usr/bin/python3

import struct
import unittest

from noisicaa.bindings import lv2
from . import buffers

class BufferTypeTest(unittest.TestCase):

    def test_float(self):
        bt = buffers.Float()
        self.assertEqual(len(bt), 4)

    def test_floatarray(self):
        bt = buffers.FloatArray(5)
        self.assertEqual(bt.size, 5)
        self.assertEqual(len(bt), 20)

    def test_atomdata(self):
        bt = buffers.AtomData(128)
        self.assertEqual(len(bt), 128)


class BufferTest(unittest.TestCase):
    def test_byte_access(self):
        buf = buffers.Buffer(buffers.FloatArray(4))
        self.assertEqual(
            struct.unpack('=ffff', buf.to_bytes()),
            (0.0, 0.0, 0.0, 0.0))
        buf.set_bytes(struct.pack('=ff', 1.0, 2.0))
        self.assertEqual(
            struct.unpack('=ffff', buf.to_bytes()),
            (1.0, 2.0, 0.0, 0.0))
        with self.assertRaises(AssertionError):
            buf.set_bytes(struct.pack('=fffff', 1.0, 2.0, 3.0, 4.0, 5.0))

    def test_buffer_protocol(self):
        buf = buffers.Buffer(buffers.Float())
        buf.set_bytes(struct.pack('=f', 1.0))

        v = memoryview(buf)
        self.assertEqual(v.itemsize, 1)
        self.assertEqual(v.format, 'B')
        self.assertEqual(v.nbytes, 4)
        self.assertEqual(v.ndim, 1)
        self.assertEqual(v.shape, (4,))
        self.assertEqual(v.strides, (1,))

        self.assertEqual(struct.unpack('=f', v[:]), (1.0,))

        v[:] = b'abcd'
        self.assertEqual(buf.to_bytes(), b'abcd')

    def test_clear_float(self):
        buf = buffers.Buffer(buffers.Float())
        buf.set_bytes(struct.pack('=f', 1.0))
        buf.clear()
        self.assertEqual(struct.unpack('=f', buf.to_bytes()), (0.0,))

    def test_mix_float(self):
        buf1 = buffers.Buffer(buffers.Float())
        buf1.set_bytes(struct.pack('=f', 1.0))
        buf2 = buffers.Buffer(buffers.Float())
        buf2.set_bytes(struct.pack('=f', 2.0))
        buf1.mix(buf2)
        self.assertEqual(struct.unpack('=f', buf1.to_bytes()), (3.0,))
        self.assertEqual(struct.unpack('=f', buf2.to_bytes()), (2.0,))

    def test_mul_float(self):
        buf = buffers.Buffer(buffers.Float())
        buf.set_bytes(struct.pack('=f', 2.0))
        buf.mul(3.0)
        self.assertEqual(struct.unpack('=f', buf.to_bytes()), (6.0,))

    def test_clear_floatarray(self):
        buf = buffers.Buffer(buffers.FloatArray(4))
        buf.set_bytes(struct.pack('=ffff', 1.0, 2.0, 3.0, 4.0))
        buf.clear()
        self.assertEqual(struct.unpack('=ffff', buf.to_bytes()), (0.0, 0.0, 0.0, 0.0))

    def test_mix_float(self):
        buf1 = buffers.Buffer(buffers.FloatArray(4))
        buf1.set_bytes(struct.pack('=ffff', 1.0, 2.0, 3.0, 4.0))
        buf2 = buffers.Buffer(buffers.FloatArray(4))
        buf2.set_bytes(struct.pack('=ffff', 2.0, 3.0, 4.0, 1.0))
        buf1.mix(buf2)
        self.assertEqual(struct.unpack('=ffff', buf1.to_bytes()), (3.0, 5.0, 7.0, 5.0))
        self.assertEqual(struct.unpack('=ffff', buf2.to_bytes()), (2.0, 3.0, 4.0, 1.0))

    def test_mul_float(self):
        buf = buffers.Buffer(buffers.FloatArray(4))
        buf.set_bytes(struct.pack('=ffff', 1.0, 2.0, 3.0, 4.0))
        buf.mul(3.0)
        self.assertEqual(struct.unpack('=ffff', buf.to_bytes()), (3.0, 6.0, 9.0, 12.0))

    def _fill_atom_buffer(self, buf, data):
        temp = bytearray(len(buf.type))

        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(temp, len(temp))

        urid = lv2.static_mapper.map(b'http://lv2plug.in/ns/ext/atom#String')
        with forge.sequence():
            for frames, item in data:
                forge.write_atom_event(frames, urid, item, len(item))

        buf.set_bytes(bytes(temp))

    def _read_atom_buffer(self, buf):
        result = []

        seq = lv2.wrap_atom(lv2.static_mapper, buf.to_bytes())
        for event in seq.events:
            self.assertEqual(
                event.atom.type_uri, b'http://lv2plug.in/ns/ext/atom#String')
            result.append((event.frames, event.atom.data))

        return result

    def test_clear_atomdata(self):
        buf = buffers.Buffer(buffers.AtomData(1024))
        self._fill_atom_buffer(buf, [(0, b'0'), (10, b'10'), (20, b'20'), (30, b'30')])
        buf.clear()
        self.assertEqual(self._read_atom_buffer(buf), [])

    def test_mix_atomdata(self):
        buf1 = buffers.Buffer(buffers.AtomData(1024))
        self._fill_atom_buffer(buf1, [(0, b'0'), (10, b'10'), (20, b'20'), (30, b'30')])
        buf2 = buffers.Buffer(buffers.AtomData(1024))
        self._fill_atom_buffer(buf2, [(1, b'1'), (9, b'9'), (11, b'11'), (15, b'15')])
        buf1.mix(buf2)
        self.assertEqual(
            self._read_atom_buffer(buf1),
            [(0, b'0'), (1, b'1'), (9, b'9'), (10, b'10'),
             (11, b'11'), (15, b'15'), (20, b'20'), (30, b'30')])
        self.assertEqual(
            self._read_atom_buffer(buf2),
            [(1, b'1'), (9, b'9'), (11, b'11'), (15, b'15')])

    def test_mul_atomdata(self):
        buf = buffers.Buffer(buffers.AtomData(1024))
        with self.assertRaises(TypeError):
            buf.mul(3.0)


if __name__ == '__main__':
    unittest.main()
