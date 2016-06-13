#!/usr/bin/python3

import logging
import wave
import os.path

from ...constants import DATA_DIR
from ..resample import (Resampler,
                        AV_CH_LAYOUT_MONO,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_U8,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from ..ports import AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class MetronomeSource(Node):
    def __init__(self, speed):
        super().__init__()

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._speed = speed

        self._timepos = 0
        self._buffer = None

    def setup(self):
        fp = wave.open(
            os.path.join(DATA_DIR, 'sounds', 'metronome.wav'), 'rb')

        if fp.getnchannels() == 1:
            ch_layout = AV_CH_LAYOUT_MONO
        elif fp.getnchannels() == 2:
            ch_layout = AV_CH_LAYOUT_STEREO
        else:
            raise Exception(
                "Unsupported number of channels: %d" % fp.getnchannels())

        if fp.getsampwidth() == 1:
            sample_fmt = AV_SAMPLE_FMT_U8
        elif fp.getsampwidth() == 2:
            sample_fmt = AV_SAMPLE_FMT_S16
        else:
            raise Exception(
                "Unsupported sample width: %d" % fp.getsampwidth())

        self._buffer = self._output.create_frame(0)
        # TODO: Take output format from _output.audio_format
        resampler = Resampler(
            ch_layout, sample_fmt, fp.getframerate(),
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100)

        while True:
            samples = fp.readframes(1024)
            if len(samples) == 0:
                break

            samples = resampler.convert(
                samples,
                len(samples) // (fp.getnchannels() * fp.getsampwidth()))
            self._buffer.append_samples(
                samples, len(samples) // (
                    self._buffer.audio_format.num_channels
                    * self._buffer.audio_format.bytes_per_sample))

        self._buffer.resize(self._speed)

    def run(self, timepos):
        duration = 4096

        buffer = self._output.create_frame(0)
        while len(buffer) < duration:
            fr = self._buffer.pop(min(duration - len(buffer),
                                      len(self._buffer)))
            self._buffer.append(fr)
            buffer.append(fr)

        frame = self._output.create_frame(self._timepos)
        frame.append(buffer.pop(duration))
        self._timepos += len(frame)

        logger.info('Node %s created %s', self.name, frame)
        self._output.add_frame(frame)
