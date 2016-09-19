#!/usr/bin/python3

import logging
import os
import os.path

from noisicaa import constants
from noisicaa import instrument_db

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

        description = instrument_db.InstrumentDescription(
            uri=uri,
            display_name=os.path.basename(path)[:-4])

        yield description
