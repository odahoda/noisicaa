
cdef class BufferType:
    cpdef int clear_buffer(self, char* buf) except -1
    cpdef int mix_buffers(self, const char* buf1, char* buf2) except -1
    cpdef int mul_buffer(self, char* buf, float factor) except -1


cdef class Buffer(object):
    cdef readonly BufferType type
    cdef char* data

    cpdef bytes to_bytes(self)
    cpdef int set_bytes(self, bytes data) except -1
    cpdef int clear(self) except -1
    cpdef int mix(self, Buffer other) except -1
    cpdef int mul(self, float factor) except -1
