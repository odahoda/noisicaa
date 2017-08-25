from libc.stdint cimport uint8_t, uint32_t

from noisicaa.bindings.lv2 cimport urid

from .status cimport *

cdef extern from "buffers.h" namespace "noisicaa" nogil:
    ctypedef uint8_t* BufferPtr

    cppclass BufferType:
        pass

    cppclass Float(BufferType):
        pass

    cppclass FloatAudioBlock(BufferType):
        pass

    cppclass AtomData(BufferType):
        AtomData(urid.LV2_URID_Map* map)

    cppclass Buffer:
        Buffer(BufferType* type)

        const BufferType* type() const
        BufferPtr data()
        uint32_t size() const

        Status allocate(uint32_t block_size)

        Status clear()
        Status mix(const Buffer* other)
        Status mul(float factor)
