#!/usr/bin/python3

import logging
import subprocess

from ..exceptions import Error
from ..ports import AudioInputPort
from ..node import Node
from ..node_types import NodeType
from ..resample import (Resampler,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from .. import audio_format

logger = logging.getLogger(__name__)


class EncoderError(Error):
    pass


class Encoder(object):
    def __init__(self, path):
        self.path = path

    def setup(self):
        raise NotImplementedError

    def cleanup(self):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def consume(self, frame):
        raise NotImplementedError


class FlacEncoder(Encoder):
    def __init__(self, path):
        super().__init__(path)

        self._proc = None
        self._resampler = None

    def setup(self):
        self._resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100,
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_S16, 44100)

    def cleanup(self):
        self._resampler = None

        if self._proc is not None:
            try:
                self._proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    def start(self):
        cmd = ['/usr/bin/flac',
               '--force-raw-format',
               '--endian=little',  # will this bite us on a big-endian machine?
               '--channels=2',
               '--bps=16',
               '--sign=signed',
               '--sample-rate=44100',
               '--force',
               '--output-name=%s' % self.path,
               '-']
        logger.info("Starting FLAC encoder: %s", ' '.join(cmd))
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def stop(self):
        self._proc.stdin.close()
        self._proc.wait(timeout=60)
        if self._proc.returncode != 0:
            raise EncoderError(
                "Subprocess terminated with error %d" % self._proc.returncode)
        self._proc = None

    def consume(self, frame):
        if self._proc.poll() is not None:
            raise EncoderError(
                "Subprocess terminated with error %d" % self._proc.returncode)

        samples = self._resampler.convert(frame.as_bytes(), len(frame))
        self._proc.stdin.write(samples)


class EncoderSink(Node):
    desc = NodeType()
    desc.name = 'encodersink'
    desc.port('in', 'input', 'audio')
    desc.parameter('format', 'string')
    desc.parameter('path', 'string')

    formats = {
        'flac': FlacEncoder,
    }

    def __init__(self, event_loop, output_format, path):
        super().__init__(event_loop)

        self.output_format = output_format
        self.path = path

        self._encoder = self.formats[self.output_format](path)
        self._frames_processed = None

        self._input = AudioInputPort('in', audio_format.CHANNELS_STEREO)
        self.add_input(self._input)

    async def setup(self):
        await super().setup()
        self._encoder.setup()
        self._encoder.start()

    async def cleanup(self):
        self._encoder.stop()
        self._encoder.cleanup()
        await super().cleanup()

    def run(self, framesize=4096):
        self._encoder.consume(self._input.frame)
