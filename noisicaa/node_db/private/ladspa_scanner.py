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
from typing import Iterator

from noisicaa import node_db
from noisicaa.bindings import ladspa

from . import scanner

logger = logging.getLogger(__name__)


class LadspaScanner(scanner.Scanner):
    def scan(self) -> Iterator[node_db.NodeDescription]:
        # TODO: support configurable searchpaths
        rootdirs = os.environ.get('LADSPA_PATH', '/usr/lib/ladspa')
        for rootdir in rootdirs.split(':'):
            for dirpath, _, filenames in os.walk(rootdir):
                for filename in filenames:
                    if not filename.endswith('.so'):
                        continue

                    path = os.path.join(dirpath, filename)
                    logger.info("Loading LADSPA plugins from %s", path)

                    try:
                        lib = ladspa.Library(path)
                    except ladspa.Error as exc:
                        logger.warning("Failed to load LADSPA library %s: %s", path, exc)
                        continue

                    for descriptor in lib.descriptors:  # pylint: disable=not-an-iterable
                        uri = 'ladspa://%s/%s' % (filename, descriptor.label)
                        logger.info("Adding LADSPA plugin %s", uri)

                        desc = node_db.NodeDescription()
                        desc.uri = uri
                        desc.supported = True
                        desc.display_name = descriptor.name
                        desc.type = node_db.NodeDescription.PLUGIN
                        desc.node_ui.type = 'builtin://plugin'
                        desc.builtin_icon = 'node-type-ladspa'
                        desc.processor.type = 'builtin://plugin'
                        desc.plugin.type = node_db.PluginDescription.LADSPA
                        desc.has_ui = False

                        ladspa_desc = desc.ladspa
                        ladspa_desc.library_path = path
                        ladspa_desc.label = descriptor.label

                        for port in descriptor.ports:
                            port_desc = desc.ports.add()
                            port_desc.name = port.name

                            if port.direction == ladspa.PortDirection.Input:
                                port_desc.direction = node_db.PortDescription.INPUT
                            elif port.direction == ladspa.PortDirection.Output:
                                port_desc.direction = node_db.PortDescription.OUTPUT
                            else:
                                raise ValueError(port)

                            if port.type == ladspa.PortType.Control:
                                port_desc.type = node_db.PortDescription.KRATE_CONTROL
                            elif port.type == ladspa.PortType.Audio:
                                port_desc.type = node_db.PortDescription.AUDIO
                            else:
                                raise ValueError(port)

                            if (port.type == ladspa.PortType.Control
                                    and port.direction == ladspa.PortDirection.Input):
                                lower_bound = port.lower_bound(44100)
                                upper_bound = port.upper_bound(44100)
                                default = port.default(44100)

                                value_desc = port_desc.float_value
                                # Using a fixed sample rate is pretty ugly...
                                if lower_bound is not None:
                                    value_desc.min = lower_bound
                                if upper_bound is not None:
                                    value_desc.max = upper_bound
                                if default is not None:
                                    value_desc.default = default

                        yield desc
