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
from typing import Iterable

from noisicaa import instrument_db
from noisicaa.instr import soundfont
from noisicaa.instr import riff

from . import scanner

logger = logging.getLogger(__name__)


class SoundFontScanner(scanner.Scanner):
    def scan(self, path: str) -> Iterable[instrument_db.InstrumentDescription]:
        if not path.endswith('.sf2'):
            return

        sf = soundfont.SoundFont()
        try:
            sf.parse(path)
        except riff.Error as exc:
            logger.error("Failed to parse %s: %s", path, exc)
            return

        for preset in sf.presets:
            uri = self.make_uri('sf2', path, bank=preset.bank, preset=preset.preset)
            logger.info("Adding soundfont instrument %s...", uri)

            description = instrument_db.InstrumentDescription(
                uri=uri,
                format=instrument_db.InstrumentDescription.SF2,
                path=path,
                display_name=preset.name)

            yield description
