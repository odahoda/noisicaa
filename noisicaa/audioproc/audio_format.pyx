from libc.stdint cimport uint8_t, int16_t, int32_t

from collections import abc

CHANNELS_MONO = [CHANNEL_CENTER]
CHANNELS_STEREO = [CHANNEL_LEFT, CHANNEL_RIGHT]

cdef int[SAMPLE_FMT_MAX + 1] _bytes_per_sample = [
    sizeof(uint8_t),   # SAMPLE_FMT_U8
    sizeof(int16_t),   # SAMPLE_FMT_S16
    sizeof(int32_t),   # SAMPLE_FMT_S32
    sizeof(float),     # SAMPLE_FMT_FLT
    sizeof(double),    # SAMPLE_FMT_DBL
]

cdef class AudioFormat:
    def __init__(self, channels, SampleFormat sample_fmt, int sample_rate):
        if not isinstance(channels, abc.Sequence):
            raise TypeError("channels must be a sequence")

        if len(channels) > MAX_CHANNELS:
            raise ValueError("Only %d channels supported" % MAX_CHANNELS)

        cdef Channel channel
        for idx in range(len(channels)):
            channel = channels[idx]
            if not (CHANNEL_MIN <= channel <= CHANNEL_MAX):
                raise ValueError("Invalid channel %d" % channel)
            self._channels[idx] = channel
        self.num_channels = len(channels)

        if not (SAMPLE_FMT_MIN <= sample_fmt <= SAMPLE_FMT_MAX):
            raise ValueError("Invalid sample format %s" % sample_fmt)
        self.sample_fmt = sample_fmt
        self.bytes_per_sample = _bytes_per_sample[<int>self.sample_fmt]

        if sample_rate <= 0:
            raise ValueError("Invalid sample rate %d" % sample_rate)
        self.sample_rate = sample_rate


    property channels:
        def __get__(self):
            return [self._channels[idx] for idx in range(self.num_channels)]

    def __str__(self):
        # TODO: convert ints to enum names
        return "<[%s] %s %s>" % (
            ', '.join(str(channel)
                      for channel in self._channels[:self.num_channels]),
            self.sample_fmt,
            self.sample_rate)

    def __richcmp__(self, other, op):
        if not isinstance(other, AudioFormat):
            raise TypeError(
                "Can't compare AudioFormat to %s" % type(other).__name__)

        if op not in (2, 3):
            raise TypeError("AudioFormats are not ordered")

        result = self._equals(other)
        if op == 3:
            result = not result
        return result

    def _equals(self, AudioFormat other):
        if self.num_channels != other.num_channels:
            return False

        for idx in range(self.num_channels):
            if self._channels[idx] != other._channels[idx]:
                return False

        if self.sample_fmt != other.sample_fmt:
            return False

        if self.sample_rate != other.sample_rate:
            return False

        return True
