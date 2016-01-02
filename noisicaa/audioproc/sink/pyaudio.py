#!/usr/bin/python3

import logging
import time

import pyaudio

from ..resample import (Resampler,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from ..ports import AudioInputPort
from ..node import Node

logger = logging.getLogger(__name__)


class PyAudioSink(Node):
    def __init__(self):
        super().__init__()

        self._input = AudioInputPort('in')
        self.add_input(self._input)

        self._audio = None
        self._stream = None
        self._resampler = None

        self._status_listeners = []

    def add_status_listener(self, listener):
        with self.pipeline.writer_lock():
            self._status_listeners.append(listener)

    def setup(self):
        super().setup()

        self._audio = pyaudio.PyAudio()

        ch_layout = AV_CH_LAYOUT_STEREO
        sample_fmt = AV_SAMPLE_FMT_S16
        sample_rate = 44100

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=sample_rate,
            output=True)

        # use format of input buffer
        self._resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100,
            ch_layout, sample_fmt, sample_rate)

    def cleanup(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None

        if self._audio is not None:
            self._audio.terminate()
            self._audio = None

        self._resampler = None

    def run(self):
        # Sinks don't use run(), but I have to define this, to make pylint
        # happy.
        raise RuntimeError

    def consume(self, framesize=4096):
        t1 = time.time()
        fr = self._input.get_frame(framesize)
        t2 = time.time()

        wall_time_ms = 1000.0 * (t2 - t1)
        audio_time_ms = 1000.0 * len(fr) / fr.audio_format.sample_rate
        if audio_time_ms > 0:
            utilization = wall_time_ms / audio_time_ms
            with self.pipeline.reader_lock():
                for listener in self._status_listeners:
                    listener(utilization)

        # logger.debug("%.2fms to produce %.2fms of audio (%d samples)",
        #              1000.0 * (time.time() - t1),
        #              1000.0 * len(fr) / fr.audio_format.sample_rate,
        #              len(fr))

        samples = self._resampler.convert(fr.as_bytes(), len(fr))
        self._stream.write(samples)
        return fr.timepos
