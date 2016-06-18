#!/usr/bin/python3

import logging

import pyaudio

from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)
from .node import Node
from .node_types import NodeType
from .ports import AudioInputPort

logger = logging.getLogger(__name__)


class AudioSinkNode(Node):
    desc = NodeType()
    desc.name = 'audiosink'
    desc.port('in', 'input', 'audio')

    def __init__(self):
        super().__init__()

        self._input = AudioInputPort('in')
        self.add_input(self._input)

    def run(self, timepos):
        self.pipeline.backend.wait()
        self.pipeline.backend.write(self._input.frame)


class Backend(object):
    def __init__(self):
        pass

    def setup(self):
        pass

    def cleanup(self):
        pass

    def wait(self):
        raise NotImplementedError

    def write(self, frame):
        raise NotImplementedError


class NullBackend(Backend):
    def wait(self):
        pass

    def write(self, frame):
        pass


class PyAudioBackend(Backend):
    def __init__(self):
        super().__init__()

        self._audio = None
        self._stream = None
        self._resampler = None

    def setup(self):
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

    def wait(self):
        pass

    def write(self, frame):
        samples = self._resampler.convert(frame.as_bytes(), len(frame))
        self._stream.write(samples)
