#!/usr/bin/python3

from libc.stdint cimport uint32_t, uint8_t
from libc cimport string
from libc cimport stdlib
cimport cpython
cimport cpython.mem
cimport cython

from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 cimport urid


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

    cdef int clear_buffer(self, char* buf) nogil except -1:
        with gil:
            raise NotImplementedError

    cdef int mix_buffers(self, const char* buf1, char* buf2) nogil except -1:
        with gil:
            raise NotImplementedError

    cdef int mul_buffer(self, char* buf, float factor) nogil except -1:
        with gil:
            raise NotImplementedError


@cython.final
cdef class Float(BufferType):
    def __str__(self):
        return 'float'

    def __len__(self):
        return 4

    cdef int clear_buffer(self, char* buf) nogil except -1:
        (<float*>buf)[0] = 0.0
        return 0

    cdef int mix_buffers(self, const char* buf1, char* buf2) nogil except -1:
        (<float*>buf2)[0] += (<float*>buf1)[0]
        return 0

    cdef int mul_buffer(self, char* buf, float factor) nogil except -1:
        (<float*>buf)[0] *= factor
        return 0


@cython.final
cdef class FloatArray(BufferType):
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

    cdef int clear_buffer(self, char* buf) nogil except -1:
        for i in range(self.__size):
            (<float*>buf)[i] = 0.0
        return 0

    cdef int mix_buffers(self, const char* buf1, char* buf2) nogil except -1:
        for i in range(self.__size):
            (<float*>buf2)[i] += (<float*>buf1)[i]
        return 0

    cdef int mul_buffer(self, char* buf, float factor) nogil except -1:
        for i in range(self.__size):
            (<float*>buf)[i] *= factor
        return 0


@cython.final
cdef class AtomData(BufferType):
    def __init__(self, size):
        super().__init__()

        self.__size = size

        self.__mapper = urid.get_static_mapper()
        self.__frame_time_urid = self.__mapper.map(
            b'http://lv2plug.in/ns/ext/atom#frameTime')
        self.__sequence_urid = self.__mapper.map(
            b'http://lv2plug.in/ns/ext/atom#Sequence')
        self.__map = urid.URID_Map_Feature(self.__mapper)
        atom.lv2_atom_forge_init(&self.__forge, &self.__map.data)
        self.__merged = <uint8_t*>cpython.mem.PyMem_Malloc(self.__size)

    def __dealloc__(self):
        if self.__merged != NULL:
            cpython.mem.PyMem_Free(self.__merged)
            self.__merged = NULL

    def __str__(self):
        return 'atom[%d]' % self.__size

    def __len__(self):
        return self.__size

    cdef int clear_buffer(self, char* buf) nogil except -1:
        cdef atom.LV2_Atom_Forge_Frame frame
        atom.lv2_atom_forge_set_buffer(&self.__forge, <uint8_t*>buf, self.__size)
        atom.lv2_atom_forge_sequence_head(
            &self.__forge, &frame, self.__frame_time_urid)
        atom.lv2_atom_forge_pop(&self.__forge, &frame)
        return 0

    cdef int mix_buffers(self, const char* buf1, char* buf2) nogil except -1:
        cdef:
            atom.LV2_Atom_Sequence* seq1
            atom.LV2_Atom_Event* event1
            atom.LV2_Atom_Sequence* seq2
            atom.LV2_Atom_Event* event2
            atom.LV2_Atom_Forge_Frame frame
            atom.LV2_Atom_Event* event

        seq1 = <atom.LV2_Atom_Sequence*>buf1
        if seq1.atom.type != self.__sequence_urid:
            with gil:
                raise TypeError(
                    "Excepted sequence, got %s"
                    % self.__mapper.unmap(seq1.atom.type))
        event1 = atom.lv2_atom_sequence_begin(&seq1.body)

        seq2 = <atom.LV2_Atom_Sequence*>buf2
        if seq2.atom.type != self.__sequence_urid:
            with gil:
                raise TypeError(
                    "Excepted sequence, got %s"
                    % self.__mapper.unmap(seq2.atom.type))
        event2 = atom.lv2_atom_sequence_begin(&seq2.body)

        atom.lv2_atom_forge_set_buffer(&self.__forge, self.__merged, self.__size)

        atom.lv2_atom_forge_sequence_head(
            &self.__forge, &frame, self.__frame_time_urid)

        while (not atom.lv2_atom_sequence_is_end(&seq1.body, seq1.atom.size, event1)
               and not atom.lv2_atom_sequence_is_end(&seq2.body, seq2.atom.size, event2)):
            if event1.time.frames <= event2.time.frames:
                event = event1
                event1 = atom.lv2_atom_sequence_next(event1)
            else:
                event = event2
                event2 = atom.lv2_atom_sequence_next(event2)

            atom.lv2_atom_forge_frame_time(&self.__forge, event.time.frames)
            atom.lv2_atom_forge_primitive(&self.__forge, &event.body)

        while not atom.lv2_atom_sequence_is_end(&seq1.body, seq1.atom.size, event1):
            atom.lv2_atom_forge_frame_time(&self.__forge, event1.time.frames)
            atom.lv2_atom_forge_primitive(&self.__forge, &event1.body)
            event1 = atom.lv2_atom_sequence_next(event1)

        while not atom.lv2_atom_sequence_is_end(&seq2.body, seq2.atom.size, event2):
            atom.lv2_atom_forge_frame_time(&self.__forge, event2.time.frames)
            atom.lv2_atom_forge_primitive(&self.__forge, &event2.body)
            event2 = atom.lv2_atom_sequence_next(event2)

        atom.lv2_atom_forge_pop(&self.__forge, &frame)

        string.memmove(buf2, self.__merged, self.__size)
        return 0

    cdef int mul_buffer(self, char* buf, float factor) nogil except -1:
        with gil:
            raise TypeError("Operation not supported for AtomData")


cdef class Buffer(object):
    def __init__(self, buf_type):
        self.type = buf_type
        self.data = <char*>cpython.mem.PyMem_Malloc(len(self.type))
        self.type.clear_buffer(self.data)

    def __dealloc__(self):
        if self.data != NULL:
            cpython.mem.PyMem_Free(self.data)
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
