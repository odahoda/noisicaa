#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Dict, Iterable, Any  # pylint: disable=unused-import

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

        properties = {}  # type: Dict[instrument_db.Property, Any]
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
