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
from ..node_types import NodeType

logger = logging.getLogger(__name__)


class PyAudioSink(Node):
    desc = NodeType()
    desc.name = 'pyaudiosink'
    desc.port('in', 'input', 'audio')

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

    def run(self, timepos):
        fr = self._input.frame
        samples = self._resampler.convert(fr.as_bytes(), len(fr))
        self._stream.write(samples)

