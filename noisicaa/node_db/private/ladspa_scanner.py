#!/usr/bin/python3

import logging
import os
import os.path

from noisicaa import constants
from noisicaa import node_db
from noisicaa.bindings import ladspa

from . import scanner

logger = logging.getLogger(__name__)


class LadspaScanner(scanner.Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def scan(self):
        # TODO: support configurable searchpaths
        rootdir = '/usr/lib/ladspa'
        for dirpath, dirnames, filenames in os.walk(rootdir):
            for filename in filenames:
                if not filename.endswith('.so'):
                    continue

                path = os.path.join(rootdir, filename)
                logger.info("Loading LADSPA plugins from %s", path)

                try:
                    lib = ladspa.Library(path)
                except ladspa.Error as exc:
                    logger.warning("Failed to load LADSPA library %s: %s", path, exc)
                    continue

                for desc in lib.descriptors:
                    uri = 'ladspa://%s/%s' % (filename, desc.label)
                    logger.info("Added LADSPA plugin %s", uri)

                    ports = []
                    parameters = []
                    # TODO: fill in ports and parameters from descriptor

                    parameters.append(
                        node_db.InternalParameterDescription(
                            name='library_path', value=path))
                    parameters.append(
                        node_db.InternalParameterDescription(
                            name='label', value=desc.label))

                    node_desc = node_db.UserNodeDescription(
                        display_name=desc.name,
                        node_cls='ladspa',
                        ports=ports,
                        parameters=parameters)

                    yield uri, node_desc

