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
        # TODO: merge the two buffers (assuming they are sequences).
        buf1[:] = buf2[:]
