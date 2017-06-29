#!/usr/bin/python3

import numpy

from noisicaa.bindings import lv2


class BufferType(object):
    def __init__(self):
        pass

    def __eq__(self, other):
        return str(self) == str(other)

    def __str__(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def make_view(self, buf):
        raise NotImplementedError

    def clear_buffer(self, buf):
        raise NotImplementedError

    def mix_buffers(self, buf1, buf2):
        raise NotImplementedError


class Float(BufferType):
    def __str__(self):
        return 'float'

    def __len__(self):
        return 4

    def make_view(self, buf):
        return numpy.frombuffer(buf, dtype=numpy.float32, offset=0, count=1)

    def clear_buffer(self, buf):
        buf[0:4] = bytes([0,0,0,0])

    def mix_buffers(self, buf1, buf2):
        view1 = self.make_view(buf1)
        view2 = self.make_view(buf2)
        view1 += view2


class FloatArray(BufferType):
    def __init__(self, size):
        super().__init__()

        self.__size = size

    def __str__(self):
        return 'float[%d]' % self.__size

    def __len__(self):
        return 4 * self.__size

    @property
    def size(self):
        return self.__size

    def make_view(self, buf):
        return numpy.frombuffer(buf, dtype=numpy.float32, offset=0, count=self.__size)

    def clear_buffer(self, buf):
        view = self.make_view(buf)
        view.fill(0.0)

    def mix_buffers(self, buf1, buf2):
        view1 = self.make_view(buf1)
        view2 = self.make_view(buf2)
        view1 += view2


class AtomData(BufferType):
    def __init__(self, size):
        super().__init__()

        self.__size = size

    def __str__(self):
        return 'atom[%d]' % self.__size

    def __len__(self):
        return self.__size

    @property
    def size(self):
        return self.__size

    def make_view(self, buf):
        return numpy.frombuffer(buf, dtype=numpy.uint8, offset=0, count=self.__size)

    def clear_buffer(self, buf):
        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(buf, self.__size)

        with forge.sequence():
            pass

    def mix_buffers(self, buf1, buf2):
        merged = bytearray(self.__size)

        seq1 = lv2.wrap_atom(lv2.static_mapper, buf1)
        events1 = seq1.events
        seq2 = lv2.wrap_atom(lv2.static_mapper, buf2)
        events2 = seq2.events

        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(merged, self.__size)

        with forge.sequence():
            idx1 = 0
            idx2 = 0
            while idx1 < len(events1) and idx2 < len(events2):
                if events1[idx1].frames <= events2[idx2].frames:
                    event = events1[idx1]
                    idx1 += 1
                else:
                    event = events2[idx2]
                    idx2 += 1
                atom = event.atom
                forge.write_atom_event(
                    event.frames,
                    atom.type_urid, atom.data, atom.size)

            for idx in range(idx1, len(events1)):
                event = events1[idx]
                atom = event.atom
                forge.write_atom_event(
                    event.frames,
                    atom.type_urid, atom.data, atom.size)

            for idx in range(idx2, len(events2)):
                event = events2[idx]
                atom = event.atom
                forge.write_atom_event(
                    event.frames,
                    atom.type_urid, atom.data, atom.size)

        buf1[:] = merged
