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
from xml.etree import ElementTree
from typing import Iterator, Tuple

from noisicaa import constants
from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class CSoundScanner(scanner.Scanner):
    def scan(self) -> Iterator[Tuple[str, node_db.NodeDescription]]:
        rootdir = os.path.join(constants.DATA_DIR, 'csound')
        for dirpath, _, filenames in os.walk(rootdir):
            for filename in filenames:
                if not filename.endswith('.csnd'):
                    continue

                uri = 'builtin://csound/%s' % filename[:-5]

                path = os.path.join(dirpath, filename)
                logger.info("Loading csound node %s from %s", uri, path)

                tree = ElementTree.parse(path)
                root = tree.getroot()
                assert root.tag == 'csound'

                desc = node_db.NodeDescription()
                desc.supported = True
                desc.node_ui.type = node_db.NodeUIDescription.PLUGIN
                desc.type = node_db.NodeDescription.PROCESSOR
                desc.processor.type = node_db.ProcessorDescription.CSOUND

                desc.display_name = ''.join(root.find('display-name').itertext())

                desc.has_ui = False

                for port_elem in root.find('ports').findall('port'):
                    port_desc = desc.ports.add()
                    port_desc.name = port_elem.get('name')

                    display_name_elem = port_elem.find('display-name')
                    if display_name_elem is not None:
                        port_desc.display_name = ''.join(display_name_elem.itertext())

                    port_desc.type = {
                        'audio': node_db.PortDescription.AUDIO,
                        'kratecontrol': node_db.PortDescription.KRATE_CONTROL,
                        'aratecontrol': node_db.PortDescription.ARATE_CONTROL,
                        'events': node_db.PortDescription.EVENTS,
                    }[port_elem.get('type')]

                    port_desc.direction = {
                        'input': node_db.PortDescription.INPUT,
                        'output': node_db.PortDescription.OUTPUT,
                    }[port_elem.get('direction')]


                    if port_desc.direction == node_db.PortDescription.OUTPUT:
                        drywet_elem = port_elem.find('drywet')
                        if drywet_elem is not None:
                            port_desc.drywet_port = drywet_elem.get('port')
                            port_desc.drywet_default = float(drywet_elem.get('default'))

                        bypass_elem = port_elem.find('bypass')
                        if bypass_elem is not None:
                            port_desc.bypass_port = bypass_elem.get('port')

                    if (port_desc.direction == node_db.PortDescription.INPUT
                            and port_desc.type == node_db.PortDescription.EVENTS):
                        csound_elem = port_elem.find('csound')
                        if csound_elem is not None:
                            port_desc.csound_instr = csound_elem.get('instr')

                    if (port_desc.direction == node_db.PortDescription.INPUT
                            and port_desc.type == node_db.PortDescription.KRATE_CONTROL):
                        float_control_elem = port_elem.find('float-control')
                        if float_control_elem is not None:
                            value_desc = port_desc.float_value
                            min_value = float_control_elem.get('min')
                            if min_value is not None:
                                value_desc.min = float(min_value)
                            max_value = float_control_elem.get('max')
                            if max_value is not None:
                                value_desc.max = float(max_value)
                            default_value = float_control_elem.get('default')
                            if default_value is not None:
                                value_desc.default = float(default_value)

                csound_desc = desc.csound

                orchestra = ''.join(root.find('orchestra').itertext())
                orchestra = orchestra.strip() + '\n'
                csound_desc.orchestra = orchestra

                score = ''.join(root.find('score').itertext())
                score = score.strip() + '\n'
                csound_desc.score = score

                yield uri, desc
