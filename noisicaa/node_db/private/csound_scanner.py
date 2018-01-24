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

# TODO: pylint-unclean

import logging
import os
import os.path
from xml.etree import ElementTree

from noisicaa import constants
from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class CSoundScanner(scanner.Scanner):
    def scan(self):
        rootdir = os.path.join(constants.DATA_DIR, 'csound')
        for dirpath, dirnames, filenames in os.walk(rootdir):
            for filename in filenames:
                if not filename.endswith('.csnd'):
                    continue

                uri = 'builtin://csound/%s' % filename[:-5]

                path = os.path.join(rootdir, filename)
                logger.info("Loading csound node %s from %s", uri, path)

                tree = ElementTree.parse(path)
                root = tree.getroot()
                assert root.tag == 'csound'

                ports = []
                for port_elem in root.find('ports').findall('port'):
                    port_type = {
                        'audio': node_db.PortType.Audio,
                        'kratecontrol': node_db.PortType.KRateControl,
                        'aratecontrol': node_db.PortType.ARateControl,
                        'events': node_db.PortType.Events,
                    }[port_elem.get('type')]

                    direction = {
                        'input': node_db.PortDirection.Input,
                        'output': node_db.PortDirection.Output,
                    }[port_elem.get('direction')]

                    kwargs = {}

                    if direction == node_db.PortDirection.Output:
                        drywet_elem = port_elem.find('drywet')
                        if drywet_elem is not None:
                            kwargs['drywet_port'] = drywet_elem.get('port')
                            kwargs['drywet_default'] = drywet_elem.get('default')

                        bypass_elem = port_elem.find('bypass')
                        if bypass_elem is not None:
                            kwargs['bypass_port'] = bypass_elem.get('port')

                    if (direction == node_db.PortDirection.Input
                        and port_type == node_db.PortType.Events):
                        csound_elem = port_elem.find('csound')
                        if csound_elem is not None:
                            kwargs['csound_instr'] = csound_elem.get('instr')

                    if (direction == node_db.PortDirection.Input
                        and port_type == node_db.PortType.KRateControl):
                        float_control_elem = port_elem.find('float-control')
                        if float_control_elem is not None:
                            min = float_control_elem.get('min')
                            if min is not None:
                                kwargs['min'] = float(min)
                            max = float_control_elem.get('max')
                            if max is not None:
                                kwargs['max'] = float(max)
                            default = float_control_elem.get('default')
                            if default is not None:
                                kwargs['default'] = float(default)

                    port_cls = {
                        node_db.PortType.Audio: node_db.AudioPortDescription,
                        node_db.PortType.ARateControl: node_db.ARateControlPortDescription,
                        node_db.PortType.KRateControl: node_db.KRateControlPortDescription,
                        node_db.PortType.Events: node_db.EventPortDescription,
                    }[port_type]

                    port_desc = port_cls(
                        name=port_elem.get('name'),
                        direction=direction,
                        **kwargs)
                    ports.append(port_desc)

                parameters = []
                parameters_elem = root.find('parameters')
                if parameters_elem is not None:
                    for parameter_elem in parameters_elem.findall('parameter'):
                        parameter_cls = {
                            'float': node_db.FloatParameterDescription,
                        }[parameter_elem.get('type')]

                        kwargs = {}
                        kwargs['name'] = parameter_elem.get('name')
                        kwargs['display_name'] = ''.join(
                            parameter_elem.find('display-name').itertext())

                        if parameter_elem.get('type') == 'float':
                            kwargs['min'] = float(parameter_elem.get('min'))
                            kwargs['max'] = float(parameter_elem.get('max'))
                            kwargs['default'] = float(parameter_elem.get('default'))

                        parameter_desc = parameter_cls(**kwargs)
                        parameters.append(parameter_desc)

                orchestra = ''.join(root.find('orchestra').itertext())
                orchestra = orchestra.strip() + '\n'
                parameters.append(
                    node_db.StringParameterDescription(
                        name='csound_orchestra', default=orchestra, hidden=True))

                score = ''.join(root.find('score').itertext())
                score = score.strip() + '\n'
                parameters.append(
                    node_db.StringParameterDescription(
                        name='csound_score', default=score, hidden=True))

                display_name = ''.join(
                    root.find('display-name').itertext())

                node_desc = node_db.ProcessorDescription(
                    display_name=display_name,
                    processor_name='csound',
                    ports=ports,
                    parameters=parameters)

                yield uri, node_desc
