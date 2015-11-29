from libc.stdint cimport uint8_t, int16_t, int32_t

cpdef enum Channel:
    CHANNEL_CENTER  = 1
    CHANNEL_LEFT    = 2
    CHANNEL_RIGHT   = 3

    CHANNEL_MIN     = 1
    CHANNEL_MAX     = 3

cpdef enum:
    MAX_CHANNELS    = 32

cpdef enum SampleFormat:
    SAMPLE_FMT_U8   = 0      # unsigned 8 bits
    SAMPLE_FMT_S16  = 1      # signed 16 bits
    SAMPLE_FMT_S32  = 2      # signed 32 bits
    SAMPLE_FMT_FLT  = 3      # float
    SAMPLE_FMT_DBL  = 4      # double

    SAMPLE_FMT_MIN  = 0
    SAMPLE_FMT_MAX  = 4

cdef class AudioFormat:
    cdef Channel[MAX_CHANNELS] _channels
    cdef readonly int num_channels
    cdef readonly SampleFormat sample_fmt
    cdef readonly int sample_rate
    cdef readonly int bytes_per_sample
