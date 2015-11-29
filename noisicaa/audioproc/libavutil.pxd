from libc.stdint cimport int64_t, uint8_t

cdef extern from "libavutil/mem.h" nogil:
    cdef void av_freep(void *ptr)

cdef extern from "libavutil/mathematics.h" nogil:
    cdef enum AVRounding:
        AV_ROUND_ZERO     = 0
        AV_ROUND_INF      = 1
        AV_ROUND_DOWN     = 2
        AV_ROUND_UP       = 3
        AV_ROUND_NEAR_INF = 5

    cdef int64_t av_rescale_rnd(int64_t a, int64_t b, int64_t c, AVRounding)


cdef extern from "libavutil/samplefmt.h" nogil:
    cdef enum AVSampleFormat: pass

    cdef int av_get_bytes_per_sample(AVSampleFormat sample_fmt)

    cdef int av_samples_alloc(
        uint8_t **audio_data, int *linesize, int nb_channels,
        int nb_samples, AVSampleFormat sample_fmt, int align)
