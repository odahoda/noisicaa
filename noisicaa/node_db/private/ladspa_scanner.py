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

from noisicaa import node_db
from noisicaa.bindings import ladspa

from . import scanner

logger = logging.getLogger(__name__)


class LadspaScanner(scanner.Scanner):
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
                    logger.info("Adding LADSPA plugin %s", uri)

                    ports = []
                    parameters = []

                    for port in desc.ports:
                        # if (port.type == ladspa.PortType.Control
                        #         and port.direction == ladspa.PortDirection.Input):
                        #     if port.is_integer:
                        #         # TODO: this should be IntParameter
                        #         parameter_cls = node_db.FloatParameterDescription
                        #     else:
                        #         parameter_cls = node_db.FloatParameterDescription

                        #     kwargs = {}
                        #     kwargs['name'] = port.name
                        #     kwargs['display_name'] = port.name

                        #     # Using a fixed sample rate is pretty ugly...
                        #     kwargs['min'] = port.lower_bound(44100)
                        #     kwargs['max'] = port.upper_bound(44100)
                        #     default = port.default(44100)
                        #     if default is not None:
                        #         kwargs['default'] = default

                        #     parameter_desc = parameter_cls(**kwargs)
                        #     parameters.append(parameter_desc)

                        # else:
                        port_type = {
                            ladspa.PortType.Audio: node_db.PortType.Audio,
                            ladspa.PortType.Control: node_db.PortType.KRateControl,
                        }[port.type]

                        direction = {
                            ladspa.PortDirection.Input: node_db.PortDirection.Input,
                            ladspa.PortDirection.Output: node_db.PortDirection.Output,
                        }[port.direction]

                        port_cls = {
                            node_db.PortType.Audio: node_db.AudioPortDescription,
                            node_db.PortType.KRateControl: node_db.KRateControlPortDescription,
                        }[port_type]

                        kwargs = {}

                        if (port.type == ladspa.PortType.Control
                            and port.direction == ladspa.PortDirection.Input):
                            # Using a fixed sample rate is pretty ugly...
                            kwargs['min'] = port.lower_bound(44100)
                            kwargs['max'] = port.upper_bound(44100)
                            default = port.default(44100)
                            if default is not None:
                                kwargs['default'] = default

                        port_desc = port_cls(
                            name=port.name,
                            direction=direction,
                            **kwargs)
                        ports.append(port_desc)

                    parameters.append(
                        node_db.StringParameterDescription(
                            name='ladspa_library_path', default=path, hidden=True))
                    parameters.append(
                        node_db.StringParameterDescription(
                            name='ladspa_plugin_label', default=desc.label, hidden=True))

                    node_desc = node_db.ProcessorDescription(
                        display_name=desc.name,
                        processor_name='ladspa',
                        ports=ports,
                        parameters=parameters)

                    yield uri, node_desc
