from libc.stdint cimport uint8_t, int16_t, int32_t, uint64_t
from libc.string cimport memcpy, memmove, memset
from cpython cimport Py_buffer
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free
from cpython.buffer cimport PyBUF_FORMAT, PyBUF_ND, PyBUF_STRIDES

from .audio_format cimport *

import numpy


cdef class Frame:
    cdef readonly AudioFormat audio_format
    cdef readonly uint64_t timepos
    cdef public set tags
    cdef int length
    cdef uint8_t* samples
    cdef int bufsize
    cdef int _buf_count

    def __cinit__(self):
        self.length = 0
        self.samples = NULL
        self.bufsize = 0
        self._buf_count = 0

    def __dealloc__(self):
        if self.samples is not NULL:
            PyMem_Free(self.samples)
            self.samples = NULL

    def __init__(self, AudioFormat audio_format, uint64_t timepos=0, set tags=None):
        self.audio_format = audio_format
        self.timepos = timepos
        self.tags = set()
        if tags is not None:
            self.tags |= tags

    def __len__(self):
        return self.length

    def __str__(self):
        return '<frame timepos=%d length=%d>' % (self.timepos, self.length)

    property samples:
        def __get__(self):
            return numpy.asarray(self)

    def __getbuffer__(self, Py_buffer *buffer, int flags):
        cdef AudioFormat af = self.audio_format

        buffer.obj = self
        buffer.buf = <char *>self.samples
        buffer.itemsize = self.audio_format.bytes_per_sample
        buffer.len = af.bytes_per_sample * af.num_channels * self.length
        buffer.ndim = 2
        buffer.internal = NULL
        buffer.readonly = 0  # Igoring PyBUF_WRITABLE
        buffer.suboffsets = NULL

        if flags & PyBUF_FORMAT != 0:
            if af.sample_fmt == SAMPLE_FMT_U8:
                buffer.format = 'B'
            elif af.sample_fmt == SAMPLE_FMT_S16:
                buffer.format = 'h'
            elif af.sample_fmt == SAMPLE_FMT_S32:
                buffer.format = 'i'
            elif af.sample_fmt == SAMPLE_FMT_FLT:
                buffer.format = 'f'
            elif af.sample_fmt == SAMPLE_FMT_DBL:
                buffer.format = 'd'
            else:
                raise AssertionError("Bad sample format %d" % af.sample_fmt)

        if flags & PyBUF_ND != 0:
            buffer.shape = <Py_ssize_t*>PyMem_Malloc(2 * sizeof(Py_ssize_t))
            buffer.shape[0] = af.num_channels
            buffer.shape[1] = self.length
        else:
            buffer.shape = NULL

        if flags & PyBUF_STRIDES != 0:
            buffer.strides = <Py_ssize_t*>PyMem_Malloc(2 * sizeof(Py_ssize_t))
            buffer.strides[0] = buffer.itemsize
            buffer.strides[1] = buffer.itemsize * af.num_channels
        else:
            buffer.strides = NULL

        self._buf_count += 1

    def __releasebuffer__(self, Py_buffer *buffer):
        if buffer.shape is not NULL:
            PyMem_Free(buffer.shape)
        if buffer.strides is not NULL:
            PyMem_Free(buffer.strides)

        self._buf_count -= 1

    def append_samples(self, uint8_t* samples, int num):
        self._append_internal(samples, num)

    def append(self, Frame frame):
        if frame.audio_format != self.audio_format:
            raise ValueError(
                "Incompatible frame format: %s" % frame.audio_format)

        self._append_internal(frame.samples, frame.length)
        self.tags |= frame.tags

    cdef _append_internal(self, uint8_t* samples, int num):
        assert self._buf_count == 0

        cdef int bytes_needed = (num
                                 * self.audio_format.num_channels
                                 * self.audio_format.bytes_per_sample)

        if self.samples is NULL:
            # Setting initial data.
            self.samples = <uint8_t*>PyMem_Malloc(bytes_needed)
            if self.samples is NULL:
                raise MemoryError()
            memcpy(self.samples, samples, bytes_needed)
            self.length = num
            self.bufsize = bytes_needed
            return

        cdef int used_bytes = (self.length
                               * self.audio_format.num_channels
                               * self.audio_format.bytes_per_sample)
        self._grow_if_needed(used_bytes + bytes_needed)

        memcpy(self.samples + used_bytes, samples, bytes_needed)
        self.length += num

    cdef _grow_if_needed(self, int size):
        assert self._buf_count == 0

        if size <= self.bufsize:
            return

        cdef uint8_t* new_samples = <uint8_t*>PyMem_Realloc(self.samples, size)
        if new_samples is NULL:
            raise MemoryError()
        self.samples = new_samples
        self.bufsize = size

    def resize(self, int new_length):
        if new_length < self.length:
            # Shrinking. Keep current buffer, just set length to fewer samples.
            self.length = new_length

        elif new_length > self.length:
            # Growing. Add buffer to accommodate new size. Set all bytes after
            # current contents to zero.
            self._grow_if_needed(new_length
                                 * self.audio_format.num_channels
                                 * self.audio_format.bytes_per_sample)
            memset(self.samples
                   + (self.length
                      * self.audio_format.num_channels
                      * self.audio_format.bytes_per_sample),
                   0,
                   (new_length - self.length)
                   * self.audio_format.num_channels
                   * self.audio_format.bytes_per_sample)
            self.length = new_length

        else:
            # new_length == self.length, nothing to do.
            pass

    def pop(self, int num):
        if num > self.length:
            raise ValueError("Not enough elements")

        head = Frame(self.audio_format)
        head._append_internal(self.samples, num)
        if self.length > num:
            memmove(self.samples,
                    self.samples
                    + (num
                       * self.audio_format.num_channels
                       * self.audio_format.bytes_per_sample),
                    (self.length - num)
                    * self.audio_format.num_channels
                    * self.audio_format.bytes_per_sample)
        self.length -= num
        return head

    def add(self, Frame frame):
        if frame.audio_format != self.audio_format:
            raise ValueError(
                "Incompatible frame format: %s" % frame.audio_format)

        if frame.length != self.length:
            raise ValueError("Frame lengths must be identical")

        if self.audio_format.sample_fmt == SAMPLE_FMT_U8:
            self._add_u8(
                self.samples, frame.samples,
                self.length * self.audio_format.num_channels)

        elif self.audio_format.sample_fmt == SAMPLE_FMT_S16:
            self._add_s16(
                <int16_t*>self.samples, <int16_t*>frame.samples,
                self.length * self.audio_format.num_channels)

        elif self.audio_format.sample_fmt == SAMPLE_FMT_S32:
            self._add_s32(
                <int32_t*>self.samples, <int32_t*>frame.samples,
                self.length * self.audio_format.num_channels)

        elif self.audio_format.sample_fmt == SAMPLE_FMT_FLT:
            self._add_float(
                <float*>self.samples, <float*>frame.samples,
                self.length * self.audio_format.num_channels)

        elif self.audio_format.sample_fmt == SAMPLE_FMT_DBL:
            self._add_double(
                <double*>self.samples, <double*>frame.samples,
                self.length * self.audio_format.num_channels)

        else:
            raise AssertionError(
                "Bad sample format %d" % self.audio_format.sample_fmt)

        self.tags |= frame.tags

    cdef _add_u8(self, uint8_t* a, uint8_t* b, int num_samples):
        for _ in range(num_samples):
            a[0] = a[0] + b[0]
            a += 1
            b += 1

    cdef _add_s16(self, int16_t* a, int16_t* b, int num_samples):
        for _ in range(num_samples):
            a[0] = a[0] + b[0]
            a += 1
            b += 1

    cdef _add_s32(self, int32_t* a, int32_t* b, int num_samples):
        for _ in range(num_samples):
            a[0] = a[0] + b[0]
            a += 1
            b += 1

    cdef _add_float(self, float* a, float* b, int num_samples):
        for _ in range(num_samples):
            a[0] = a[0] + b[0]
            a += 1
            b += 1

    cdef _add_double(self, double* a, double* b, int num_samples):
        for _ in range(num_samples):
            a[0] = a[0] + b[0]
            a += 1
            b += 1

    def mul(self, float v):
        if self.audio_format.sample_fmt == SAMPLE_FMT_U8:
            raise NotImplementedError

        elif self.audio_format.sample_fmt == SAMPLE_FMT_S16:
            raise NotImplementedError

        elif self.audio_format.sample_fmt == SAMPLE_FMT_S32:
            raise NotImplementedError

        elif self.audio_format.sample_fmt == SAMPLE_FMT_FLT:
            self._mul_float(
                <float*>self.samples, v,
                self.length * self.audio_format.num_channels)

        elif self.audio_format.sample_fmt == SAMPLE_FMT_DBL:
            raise NotImplementedError

        else:
            raise AssertionError(
                "Bad sample format %d" % self.audio_format.sample_fmt)

    cdef _mul_float(self, float* samples, float v, int num_samples):
        for _ in range(num_samples):
            samples[0] *= v
            samples += 1

    def as_bytes(self):
        return bytes(
            self.samples[:(self.length
                           * self.audio_format.num_channels
                           * self.audio_format.bytes_per_sample)])
