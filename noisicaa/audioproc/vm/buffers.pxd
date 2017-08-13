from libc.stdint cimport uint32_t, uint8_t
from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 cimport urid

cdef class BufferType:
    cdef int clear_buffer(self, char* buf) nogil except -1
    cdef int mix_buffers(self, const char* buf1, char* buf2) nogil except -1
    cdef int mul_buffer(self, char* buf, float factor) nogil except -1

cdef class Float(BufferType):
    pass

cdef class FloatArray(BufferType):
    cdef uint32_t __size

cdef class AtomData(BufferType):
    cdef uint32_t __size
    cdef urid.URID_Mapper __mapper
    cdef urid.LV2_URID __frame_time_urid
    cdef urid.LV2_URID __sequence_urid
    cdef urid.URID_Map_Feature __map
    cdef atom.LV2_Atom_Forge __forge
    cdef uint8_t* __merged

cdef class Buffer(object):
    cdef readonly BufferType type
    cdef char* data

    cpdef bytes to_bytes(self)
    cpdef int set_bytes(self, bytes data) except -1
    cpdef int clear(self) except -1
    cpdef int mix(self, Buffer other) except -1
    cpdef int mul(self, float factor) except -1
