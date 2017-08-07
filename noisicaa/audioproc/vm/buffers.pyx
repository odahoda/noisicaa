#!/usr/bin/python3

from libc.stdint cimport uint32_t, uint8_t
from libc cimport string
from libc cimport stdlib
cimport cpython
cimport cpython.mem

from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 cimport urid
from noisicaa.bindings.lv2 import urid


cdef class BufferType(object):
    def __init__(self):
        pass

    def __richcmp__(self, other, int op):
        a = str(self)
        b = str(other)
        if op == 0:
            return a < b
        elif op == 1:
            return a <= b
        elif op == 2:
            return a == b
        elif op == 3:
            return a != b
        elif op == 4:
            return a > b
        elif op == 5:
            return a >= b

    def __str__(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    cpdef int clear_buffer(self, char* buf) except -1:
        raise NotImplementedError

    cpdef int mix_buffers(self, const char* buf1, char* buf2) except -1:
        raise NotImplementedError

    cpdef int mul_buffer(self, char* buf, float factor) except -1:
        raise NotImplementedError


cdef class Float(BufferType):
    def __str__(self):
        return 'float'

    def __len__(self):
        return 4

    cpdef int clear_buffer(self, char* buf) except -1:
        (<float*>buf)[0] = 0.0
        return 0

    cpdef int mix_buffers(self, const char* buf1, char* buf2) except -1:
        (<float*>buf2)[0] += (<float*>buf1)[0]
        return 0

    cpdef int mul_buffer(self, char* buf, float factor) except -1:
        (<float*>buf)[0] *= factor
        return 0


cdef class FloatArray(BufferType):
    cdef uint32_t __size

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

    cpdef int clear_buffer(self, char* buf) except -1:
        for i in range(self.__size):
            (<float*>buf)[i] = 0.0
        return 0

    cpdef int mix_buffers(self, const char* buf1, char* buf2) except -1:
        for i in range(self.__size):
            (<float*>buf2)[i] += (<float*>buf1)[i]
        return 0

    cpdef int mul_buffer(self, char* buf, float factor) except -1:
        for i in range(self.__size):
            (<float*>buf)[i] *= factor
        return 0


cdef class AtomData(BufferType):
    cdef uint32_t __size

    def __init__(self, size):
        super().__init__()

        self.__size = size

    def __str__(self):
        return 'atom[%d]' % self.__size

    def __len__(self):
        return self.__size

    cpdef int clear_buffer(self, char* buf) except -1:
        forge = atom.AtomForge(urid.static_mapper)
        temp = bytearray(self.__size)
        forge.set_buffer(temp, self.__size)
        with forge.sequence():
            pass
        string.memmove(buf, <char*>temp, self.__size)
        return 0

    cpdef int mix_buffers(self, const char* buf1, char* buf2) except -1:
        seq1 = atom.Atom.wrap(urid.static_mapper, <uint8_t *>buf1)
        events1 = seq1.events
        seq2 = atom.Atom.wrap(urid.static_mapper, <uint8_t *>buf2)
        events2 = seq2.events

        forge = atom.AtomForge(urid.static_mapper)
        merged = bytearray(self.__size)
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
                forge.write_atom_event(
                    event.frames,
                    event.atom.type_urid, event.atom.data, event.atom.size)

            for idx in range(idx1, len(events1)):
                event = events1[idx]
                forge.write_atom_event(
                    event.frames,
                    event.atom.type_urid, event.atom.data, event.atom.size)

            for idx in range(idx2, len(events2)):
                event = events2[idx]
                forge.write_atom_event(
                    event.frames,
                    event.atom.type_urid, event.atom.data, event.atom.size)

        string.memmove(buf2, <char*>merged, self.__size)
        return 0

    cpdef int mul_buffer(self, char* buf, float factor) except -1:
        raise TypeError("Operation not supported for AtomData")


cdef class Buffer(object):
    def __init__(self, buf_type):
        self.type = buf_type
        self.data = <char*>stdlib.malloc(len(self.type))
        self.type.clear_buffer(self.data)

    def __dealloc__(self):
        if self.data != NULL:
            stdlib.free(self.data)
            self.data = NULL

    def __getbuffer__(self, cpython.Py_buffer *buffer, int flags):
        buffer.obj = self
        buffer.buf = self.data
        buffer.itemsize = 1
        buffer.len = len(self.type)
        buffer.ndim = 1
        buffer.internal = NULL
        buffer.readonly = 0
        buffer.suboffsets = NULL
        buffer.format = 'B'
        buffer.shape = NULL
        buffer.strides = NULL

    def __releasebuffer__(self, cpython.Py_buffer *buffer):
        pass

    cpdef bytes to_bytes(self):
        return bytes(self.data[:len(self.type)])

    cpdef int set_bytes(self, bytes data) except -1:
        cdef uint32_t len_self = len(self.type)
        cdef uint32_t len_data = len(data)
        assert len_data <= len_self, '%s > %s' % (len_data, len_self)
        if len_data < len_self:
            self.type.clear_buffer(self.data)
        string.memmove(self.data, <char*>data, len_data)
        return 0

    cpdef int clear(self) except -1:
        self.type.clear_buffer(self.data)
        return 0

    cpdef int mix(self, Buffer other) except -1:
        assert self.type == other.type, '%s != %s' % (self.type, other.type)
        self.type.mix_buffers(other.data, self.data)
        return 0

    cpdef int mul(self, float factor) except -1:
        self.type.mul_buffer(self.data, factor)
        return 0
