#!/usr/bin/python3

import glob
import os
import os.path
import logging

from noisicaa import core
from noisicaa import instrument_db

from . import sample_scanner
from . import soundfont_scanner

logger = logging.getLogger(__name__)


class InstrumentDB(object):
    def __init__(self):
        self._instruments = {}
        self.listeners = core.CallbackRegistry()

    def setup(self):
        scanners = [
            sample_scanner.SampleScanner(),
            soundfont_scanner.SoundFontScanner(),
        ]

        search_paths = [
            '/usr/share/sounds/sf2/',
            ] + sorted(glob.glob('/storage/home/share/samples/ST-0?'))

        for root_path in search_paths:
            logger.info("Scanning instruments in %s...", root_path)
            for dname, dirs, files in os.walk(root_path):
                for fname in sorted(files):
                    path = os.path.join(dname, fname)
                    logger.info("Scanning file %s...", path)

                    for scanner in scanners:
                        for description in scanner.scan(path):
                            assert description.uri not in self._instruments
                            self._instruments[description.uri] = description

    def cleanup(self):
        pass

    def initial_mutations(self):
        for uri, description in sorted(self._instruments.items()):
            yield instrument_db.AddInstrumentDescription(description)

    def start_scan(self):
        pass
