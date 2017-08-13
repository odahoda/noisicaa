#!/usr/bin/python3

from libc cimport string

import logging
import wave

from noisicaa import node_db

from .. import resample
from .. cimport node
from .. import audio_format

logger = logging.getLogger(__name__)


cdef class WavFileSource(node.CustomNode):
    class_name = 'wavfile'

    def __init__(self, *, path, loop=False, end_notification=None, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.__path = path
        self.__loop = loop
        self.__end_notification = end_notification

        self.__playing = True

        self.__pos = 0
        self.__num_samples = 0
        self.__samples_l = None
        self.__samples_r = None

        self.__out_left = None
        self.__out_right = None

    def setup(self):
        super().setup()

        fp = wave.open(self.__path, 'rb')

        logger.info("%s: %s", self.__path, fp.getparams())

        self.__num_samples = fp.getnframes()

        if fp.getnchannels() == 1:
            ch_layout = resample.AV_CH_LAYOUT_MONO
        elif fp.getnchannels() == 2:
            ch_layout = resample.AV_CH_LAYOUT_STEREO
        else:
            raise Exception(
                "Unsupported number of channels: %d" % fp.getnchannels())

        if fp.getsampwidth() == 1:
            sample_fmt = resample.AV_SAMPLE_FMT_U8
        elif fp.getsampwidth() == 2:
            sample_fmt = resample.AV_SAMPLE_FMT_S16
        else:
            raise Exception(
                "Unsupported sample width: %d" % fp.getsampwidth())

        samples = fp.readframes(fp.getnframes())

        resampler = resample.Resampler(
            ch_layout, sample_fmt, fp.getframerate(),
            resample.AV_CH_LAYOUT_STEREO, resample.AV_SAMPLE_FMT_FLT, 44100)
        samples = resampler.convert(
            samples, len(samples) // (fp.getnchannels() * fp.getsampwidth()))

        # TODO: resample directly into non-interleaved buffers.
        self.__num_samples = len(samples) // 8
        self.__samples_l = bytearray(len(samples) // 2)
        self.__samples_r = bytearray(len(samples) // 2)
        for i in range(self.__num_samples):
            self.__samples_l[4*i:4*i+4] = samples[8*i:8*i+4]
            self.__samples_r[4*i:4*i+4] = samples[8*i+4:8*i+8]

        self.__pos = 0

        fp.close()

    cdef int connect_port(self, port_name, buf) except -1:
        if port_name == 'out:left':
            self.__out_left = buf
        elif port_name == 'out:right':
            self.__out_right = buf
        else:
            raise ValueError(port_name)
        return 0

    cdef int run(self, ctxt) except -1:
        cdef:
            uint32_t samples_written
            uint32_t num_samples
            uint32_t offset
            uint32_t length

        samples_written = 0

        if self.__playing:
            num_samples = min(ctxt.duration, self.__num_samples - self.__pos)
            string.memmove(
                self.__out_left.data,
                <char*>self.__samples_l + self.__pos * sizeof(float),
                num_samples * sizeof(float))
            string.memmove(
                self.__out_right.data,
                <char*>self.__samples_r + self.__pos * sizeof(float),
                num_samples * sizeof(float))

            samples_written += num_samples
            self.__pos += num_samples
            if self.__pos >= self.__num_samples:
                self.__pos = 0
                if not self.__loop:
                    self.__playing = False
                    if self.__end_notification:
                        self.send_notification(self.__end_notification)


        if samples_written < ctxt.duration:
            string.memset(
                self.__out_left.data + samples_written * sizeof(float),
                0,
                (ctxt.duration - samples_written) * sizeof(float))
            string.memset(
                self.__out_right.data + samples_written * sizeof(float),
                0,
                (ctxt.duration - samples_written) * sizeof(float))

        return 0
