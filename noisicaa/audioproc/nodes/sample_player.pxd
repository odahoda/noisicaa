from . cimport csound

cdef class SamplePlayer(csound.CSoundBase):
    cdef str __sample_path
