#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging
import os
import os.path
from typing import Iterable

from noisicaa import instrument_db
from noisicaa.instr import wave
from noisicaa.instr import riff

from . import scanner

logger = logging.getLogger(__name__)


class SampleScanner(scanner.Scanner):
    def scan(self, path: str) -> Iterable[instrument_db.InstrumentDescription]:
        if not path.endswith('.wav'):
            return

        uri = self.make_uri('sample', path)
        logger.info("Adding sample instrument %s...", uri)

        try:
            parsed = wave.WaveFile()
            parsed.parse(path)
        except riff.Error as exc:
            logger.error("Failed to parse WAVE file %s: %s", path, exc)
            return

        description = instrument_db.InstrumentDescription(
            uri=uri,
            format=instrument_db.InstrumentDescription.SAMPLE,
            path=path,
            display_name=os.path.basename(path)[:-4])

        if parsed.bits_per_sample is not None:
            description.bits_per_sample = parsed.bits_per_sample
        if parsed.channels is not None:
            description.num_channels = parsed.channels
        if parsed.sample_rate is not None:
            description.sample_rate = parsed.sample_rate
        if parsed.num_samples is not None:
            description.num_samples = parsed.num_samples
        if parsed.num_samples is not None and parsed.sample_rate is not None:
            description.duration = parsed.num_samples / parsed.sample_rate


        yield description
