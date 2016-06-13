#!/usr/bin/python3

import logging
import wave

from ..exceptions import EndOfStreamError
from ..resample import (Resampler,
                        AV_CH_LAYOUT_MONO,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_U8,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from ..ports import AudioOutputPort
from ..node import Node
from ..frame import Frame

logger = logging.getLogger(__name__)


class WavFileSource(Node):
    def __init__(self, path):
        super().__init__()

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._path = path
        self._fp = None
        self._start_pos = None
        self._timepos = None
        self._resampler = None

    def setup(self):
        super().setup()

        self._fp = wave.open(self._path, 'rb')
        self._start_pos = self._fp.tell()
        self._timepos = 0

        logger.info("%s: %s", self._path, self._fp.getparams())

        if self._fp.getnchannels() == 1:
            ch_layout = AV_CH_LAYOUT_MONO
        elif self._fp.getnchannels() == 2:
            ch_layout = AV_CH_LAYOUT_STEREO
        else:
            raise Exception(
                "Unsupported number of channels: %d" % self._fp.getnchannels())

        if self._fp.getsampwidth() == 1:
            sample_fmt = AV_SAMPLE_FMT_U8
        elif self._fp.getsampwidth() == 2:
            sample_fmt = AV_SAMPLE_FMT_S16
        else:
            raise Exception(
                "Unsupported sample width: %d" % self._fp.getsampwidth())

        # TODO: Take output format from _output.audio_format
        self._resampler = Resampler(
            ch_layout, sample_fmt, self._fp.getframerate(),
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100)

    def cleanup(self):
        super().cleanup()

        if self._fp is not None:
            self._fp.close()
            self._fp = None

        self._resampler = None

    def run(self, timepos):
        samples = self._fp.readframes(4096)
        if len(samples) == 0:
            raise EndOfStreamError

        samples = self._resampler.convert(
            samples, len(samples) // (self._fp.getnchannels()
                                      * self._fp.getsampwidth()))

        frame = Frame(self._output.audio_format, 0, set())
        frame.append_samples(
            samples,
            len(samples) // (
                # pylint thinks that frame.audio_format is a class object.
                # pylint: disable=E1101
                frame.audio_format.num_channels
                * frame.audio_format.bytes_per_sample))
        assert len(frame) <= 4096
        frame.resize(4096)

        self._output.frame.copy_from(frame)
