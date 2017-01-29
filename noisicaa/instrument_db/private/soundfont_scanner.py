#!/usr/bin/python3

import logging
import os
import os.path
import urllib.parse

from noisicaa import constants
from noisicaa import instrument_db
from noisicaa.instr import soundfont
from noisicaa.instr import riff

from . import scanner

logger = logging.getLogger(__name__)


class SoundFontScanner(scanner.Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def scan(self, path):
        if not path.endswith('.sf2'):
            return

        sf = soundfont.SoundFont()
        try:
            sf.parse(path)
        except riff.Error as exc:
            logger.error("Failed to parse %s: %s" % (path, exc))
            return

        for preset in sf.presets:
            uri = self.make_uri('sf2', path, bank=preset.bank, preset=preset.preset)
            logger.info("Adding soundfont instrument %s...", uri)

            description = instrument_db.InstrumentDescription(
                uri=uri,
                path=path,
                display_name=preset.name,
                properties={})

            yield description
