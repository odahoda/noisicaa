#!/usr/bin/python3

import numpy


class BufferType(object):
    def __init__(self):
        pass

    def __str__(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def make_view(self, buf):
        raise NotImplementedError


class Float(BufferType):
    def __str__(self):
        return 'float'

    def __len__(self):
        return 4

    def make_view(self, buf):
        return numpy.frombuffer(buf, dtype=numpy.float32, offset=0, count=1)


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
