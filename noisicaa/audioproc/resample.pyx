from libc.stdint cimport int64_t, uint8_t

from .libavutil cimport *
from .libswresample cimport *
from .frame import *

__version__ = 'libswresample %d' % swresample_version()
__configuration__ = str(swresample_configuration(), 'ascii')
__license__ = str(swresample_license(), 'ascii')

## from libavutil/samplefmt.h
#
# Sample formats
cpdef enum:
    AV_SAMPLE_FMT_U8   = 0      # unsigned 8 bits
    AV_SAMPLE_FMT_S16  = 1      # signed 16 bits
    AV_SAMPLE_FMT_S32  = 2      # signed 32 bits
    AV_SAMPLE_FMT_FLT  = 3      # float
    AV_SAMPLE_FMT_DBL  = 4      # double
    AV_SAMPLE_FMT_U8P  = 5      # unsigned 8 bits, planar
    AV_SAMPLE_FMT_S16P = 6      # signed 16 bits, planar
    AV_SAMPLE_FMT_S32P = 7      # signed 32 bits, planar
    AV_SAMPLE_FMT_FLTP = 8      # float, planar
    AV_SAMPLE_FMT_DBLP = 9      # double, planar

## from libavutil/channel_layout.h
#
# Audio channel masks
# A channel layout is a 64-bits integer with a bit set for every channel.
# The number of bits set must be equal to the number of channels.
# The value 0 means that the channel layout is not known.
# Note: this data structure is not powerful enough to handle channels
# combinations that have the same channel multiple times, such as
# dual-mono.
AV_CH_FRONT_LEFT             = 0x00000001
AV_CH_FRONT_RIGHT            = 0x00000002
AV_CH_FRONT_CENTER           = 0x00000004
AV_CH_LOW_FREQUENCY          = 0x00000008
AV_CH_BACK_LEFT              = 0x00000010
AV_CH_BACK_RIGHT             = 0x00000020
AV_CH_FRONT_LEFT_OF_CENTER   = 0x00000040
AV_CH_FRONT_RIGHT_OF_CENTER  = 0x00000080
AV_CH_BACK_CENTER            = 0x00000100
AV_CH_SIDE_LEFT              = 0x00000200
AV_CH_SIDE_RIGHT             = 0x00000400
AV_CH_TOP_CENTER             = 0x00000800
AV_CH_TOP_FRONT_LEFT         = 0x00001000
AV_CH_TOP_FRONT_CENTER       = 0x00002000
AV_CH_TOP_FRONT_RIGHT        = 0x00004000
AV_CH_TOP_BACK_LEFT          = 0x00008000
AV_CH_TOP_BACK_CENTER        = 0x00010000
AV_CH_TOP_BACK_RIGHT         = 0x00020000
AV_CH_STEREO_LEFT            = 0x20000000  # Stereo downmix.
AV_CH_STEREO_RIGHT           = 0x40000000  # See AV_CH_STEREO_LEFT.
AV_CH_WIDE_LEFT              = 0x0000000080000000
AV_CH_WIDE_RIGHT             = 0x0000000100000000
AV_CH_SURROUND_DIRECT_LEFT   = 0x0000000200000000
AV_CH_SURROUND_DIRECT_RIGHT  = 0x0000000400000000
AV_CH_LOW_FREQUENCY_2        = 0x0000000800000000

# Audio channel layouts
AV_CH_LAYOUT_MONO               = (AV_CH_FRONT_CENTER)
AV_CH_LAYOUT_STEREO             = (AV_CH_FRONT_LEFT | AV_CH_FRONT_RIGHT)
AV_CH_LAYOUT_2POINT1            = (AV_CH_LAYOUT_STEREO | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_2_1                = (AV_CH_LAYOUT_STEREO | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_SURROUND           = (AV_CH_LAYOUT_STEREO | AV_CH_FRONT_CENTER)
AV_CH_LAYOUT_3POINT1            = (AV_CH_LAYOUT_SURROUND | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_4POINT0            = (AV_CH_LAYOUT_SURROUND | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_4POINT1            = (AV_CH_LAYOUT_4POINT0 | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_2_2                = (AV_CH_LAYOUT_STEREO | AV_CH_SIDE_LEFT
                                   | AV_CH_SIDE_RIGHT)
AV_CH_LAYOUT_QUAD               = (AV_CH_LAYOUT_STEREO | AV_CH_BACK_LEFT
                                   | AV_CH_BACK_RIGHT)
AV_CH_LAYOUT_5POINT0            = (AV_CH_LAYOUT_SURROUND | AV_CH_SIDE_LEFT
                                   | AV_CH_SIDE_RIGHT)
AV_CH_LAYOUT_5POINT1            = (AV_CH_LAYOUT_5POINT0 | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_5POINT0_BACK       = (AV_CH_LAYOUT_SURROUND | AV_CH_BACK_LEFT
                                   | AV_CH_BACK_RIGHT)
AV_CH_LAYOUT_5POINT1_BACK       = (AV_CH_LAYOUT_5POINT0_BACK
                                   | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_6POINT0            = (AV_CH_LAYOUT_5POINT0 | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_6POINT0_FRONT      = (AV_CH_LAYOUT_2_2
                                   | AV_CH_FRONT_LEFT_OF_CENTER
                                   | AV_CH_FRONT_RIGHT_OF_CENTER)
AV_CH_LAYOUT_HEXAGONAL          = (AV_CH_LAYOUT_5POINT0_BACK
                                   | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_6POINT1            = (AV_CH_LAYOUT_5POINT1 | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_6POINT1_BACK       = (AV_CH_LAYOUT_5POINT1_BACK
                                   | AV_CH_BACK_CENTER)
AV_CH_LAYOUT_6POINT1_FRONT      = (AV_CH_LAYOUT_6POINT0_FRONT
                                   | AV_CH_LOW_FREQUENCY)
AV_CH_LAYOUT_7POINT0            = (AV_CH_LAYOUT_5POINT0 | AV_CH_BACK_LEFT
                                   | AV_CH_BACK_RIGHT)
AV_CH_LAYOUT_7POINT0_FRONT      = (AV_CH_LAYOUT_5POINT0
                                   | AV_CH_FRONT_LEFT_OF_CENTER
                                   | AV_CH_FRONT_RIGHT_OF_CENTER)
AV_CH_LAYOUT_7POINT1            = (AV_CH_LAYOUT_5POINT1 | AV_CH_BACK_LEFT
                                   | AV_CH_BACK_RIGHT)
AV_CH_LAYOUT_7POINT1_WIDE       = (AV_CH_LAYOUT_5POINT1
                                   | AV_CH_FRONT_LEFT_OF_CENTER
                                   | AV_CH_FRONT_RIGHT_OF_CENTER)
AV_CH_LAYOUT_7POINT1_WIDE_BACK  = (AV_CH_LAYOUT_5POINT1_BACK
                                   | AV_CH_FRONT_LEFT_OF_CENTER
                                   | AV_CH_FRONT_RIGHT_OF_CENTER)
AV_CH_LAYOUT_OCTAGONAL          = (AV_CH_LAYOUT_5POINT0 | AV_CH_BACK_LEFT
                                   | AV_CH_BACK_CENTER | AV_CH_BACK_RIGHT)
AV_CH_LAYOUT_HEXADECAGONAL      = (AV_CH_LAYOUT_OCTAGONAL | AV_CH_WIDE_LEFT
                                   | AV_CH_WIDE_RIGHT | AV_CH_TOP_BACK_LEFT
                                   | AV_CH_TOP_BACK_RIGHT
                                   | AV_CH_TOP_BACK_CENTER
                                   | AV_CH_TOP_FRONT_CENTER
                                   | AV_CH_TOP_FRONT_LEFT
                                   | AV_CH_TOP_FRONT_RIGHT)
AV_CH_LAYOUT_STEREO_DOWNMIX     = (AV_CH_STEREO_LEFT | AV_CH_STEREO_RIGHT)


cdef int num_channels(int64_t layout):
    cdef int channels = 0
    while layout:
        if layout & 1:
            channels += 1
        layout >>= 1
    return channels


cdef class Resampler:
    cdef SwrContext* _ctx
    cdef int64_t in_ch_layout
    cdef int in_num_channels
    cdef AVSampleFormat in_sample_fmt
    cdef int in_sample_rate
    cdef int64_t out_ch_layout
    cdef int out_num_channels
    cdef AVSampleFormat out_sample_fmt
    cdef int out_sample_rate

    def __cinit__(self):
        self._ctx = NULL

    def __dealloc__(self):
        if self._ctx is not NULL:
            swr_free(&self._ctx)

    def __init__(self,
                 in_ch_layout, in_sample_fmt, in_sample_rate,
                 out_ch_layout, out_sample_fmt, out_sample_rate):
        self.in_ch_layout = in_ch_layout
        self.in_num_channels = num_channels(in_ch_layout)
        self.in_sample_fmt = in_sample_fmt
        self.in_sample_rate = in_sample_rate
        self.out_ch_layout = out_ch_layout
        self.out_num_channels = num_channels(out_ch_layout)
        self.out_sample_fmt = out_sample_fmt
        self.out_sample_rate = out_sample_rate

        self._ctx = swr_alloc_set_opts(
            NULL,
            out_ch_layout, out_sample_fmt, out_sample_rate,
            in_ch_layout, in_sample_fmt, in_sample_rate,
            0, NULL
        )
        if self._ctx is NULL:
            raise MemoryError

        err = swr_init(self._ctx)
        if err != 0:
            raise Exception("Failed to initialize SwrContext: %d" % err)

    def convert(self, const uint8_t* samples, int in_count):
        cdef const uint8_t* in_buffer[32]
        in_buffer[0] = samples
        for i in range(1, 32):
            in_buffer[i] = NULL

        cdef int out_count = av_rescale_rnd(
            swr_get_delay(self._ctx, self.in_sample_rate) + in_count,
            self.out_sample_rate, self.in_sample_rate, AV_ROUND_UP)
        cdef uint8_t* out_buffer[32]
        for i in range(0, 32):
            out_buffer[i] = NULL

        cdef int out_bufsize = av_samples_alloc(
            out_buffer, NULL,
            self.out_num_channels, out_count, self.out_sample_fmt,
            0)
        if out_bufsize < 0:
            # TODO: Check if error is really ENOMEM
            raise MemoryError

        cdef int out_samples
        try:
            result = bytes()
            while True:
                out_samples = swr_convert(
                    self._ctx, out_buffer, out_count, in_buffer, in_count)
                if out_samples == 0:
                    break

                if out_samples < 0:
                    raise Exception("swr_convert failed: %d" % out_samples)

                out_bytes = (
                    out_samples
                    * self.out_num_channels
                    * av_get_bytes_per_sample(self.out_sample_fmt))
                result = result + bytes(out_buffer[0][:out_bytes])

                in_count = 0

        finally:
            for i in range(32):
                if out_buffer[i] is not NULL:
                    av_freep(&out_buffer[0])

        return result

    def flush(self):
        cdef int out_count = 100
        cdef uint8_t* out_buffer[32]
        for i in range(0, 32):
            out_buffer[i] = NULL

        cdef int out_bufsize = av_samples_alloc(
            out_buffer, NULL,
            self.out_num_channels, out_count, self.out_sample_fmt,
            0)
        cdef int out_samples
        try:
            result = bytes()
            while True:
                out_samples = swr_convert(
                    self._ctx, out_buffer, out_count, NULL, 0)
                if out_samples == 0:
                    break

                if out_samples < 0:
                    raise Exception("swr_convert failed: %d" % out_samples)

                out_bytes = (
                    out_samples
                    * self.out_num_channels
                    * av_get_bytes_per_sample(self.out_sample_fmt))
                result = result + bytes(out_buffer[0][:out_bytes])

        finally:
            for i in range(32):
                if out_buffer[i] is not NULL:
                    av_freep(&out_buffer[0])

        return result

