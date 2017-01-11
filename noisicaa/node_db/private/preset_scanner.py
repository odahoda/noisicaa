#!/usr/bin/python3

import logging
import os
import os.path
from xml.etree import ElementTree

from noisicaa import constants
from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class PresetScanner(scanner.Scanner):
    def __init__(self, nodes, **kwargs):
        super().__init__(**kwargs)

        self.__nodes = nodes

    def scan(self):
        search_paths = [
            os.path.join(constants.DATA_DIR, 'presets'),
            os.path.join(os.path.expanduser('~'), '.noisicaä', 'presets'),
        ]

        node_factory = self.__nodes.get

        for search_path in search_paths:
            if not os.path.isdir(search_path):
                logger.warning("Preset directory %s does not exist, skipping.", search_path)
                continue

            logger.info("Loading presets from %s...", search_path)
            for dirpath, dirnames, filenames in os.walk(search_path):
                for filename in filenames:
                    if not filename.endswith('.preset'):
                        continue

                    uri = 'preset://%s' % filename[:-7]
                    path = os.path.join(dirpath, filename)

                    try:
                        preset = node_db.Preset.from_file(path, node_factory)
                    except node_db.PresetLoadError as exc:
                        logger.error("Failed to load preset %s: %s", uri, path)
                    else:
                        yield uri, preset
