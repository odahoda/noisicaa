#!/usr/bin/python3

import logging
import os
import os.path

from noisicaa import constants
from noisicaa import instrument_db
from noisicaa.instr import wave
from noisicaa.instr import riff

from . import scanner

logger = logging.getLogger(__name__)


class SampleScanner(scanner.Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def scan(self, path):
        if not path.endswith('.wav'):
            return

        uri = self.make_uri('sample', path)
        logger.info("Adding sample instrument %s...", uri)

        try:
            parsed = wave.WaveFile().parse(path)
        except riff.Error as exc:
            logger.error("Failed to parse WAVE file %s: %s", path, exc)
            return

        properties = {}
        if parsed.bits_per_sample is not None:
            properties[instrument_db.Property.BitsPerSample] = parsed.bits_per_sample
        if parsed.channels is not None:
            properties[instrument_db.Property.NumChannels] = parsed.channels
        if parsed.sample_rate is not None:
            properties[instrument_db.Property.SampleRate] = parsed.sample_rate
        if parsed.num_samples is not None:
            properties[instrument_db.Property.NumSamples] = parsed.num_samples
        if parsed.num_samples is not None and parsed.sample_rate is not None:
            properties[instrument_db.Property.Duration] = parsed.num_samples / parsed.sample_rate

        description = instrument_db.InstrumentDescription(
            uri=uri,
            path=path,
            display_name=os.path.basename(path)[:-4],
            properties=properties)

        yield description
