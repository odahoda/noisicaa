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
                    logger.info("Adding LADSPA plugin %s", uri)

                    ports = []
                    parameters = []

                    for port in desc.ports:
                        if (port.type == ladspa.PortType.Control
                                and port.direction == ladspa.PortDirection.Input):
                            if port.is_integer:
                                # TODO: this should be IntParameter
                                parameter_cls = node_db.FloatParameterDescription
                            else:
                                parameter_cls = node_db.FloatParameterDescription

                            kwargs = {}
                            kwargs['name'] = port.name
                            kwargs['display_name'] = port.name

                            # Using a fixed sample rate is pretty ugly...
                            kwargs['min'] = port.lower_bound(44100)
                            kwargs['max'] = port.upper_bound(44100)
                            default = port.default(44100)
                            if default is not None:
                                kwargs['default'] = default

                            parameter_desc = parameter_cls(**kwargs)
                            parameters.append(parameter_desc)

                        else:
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

                            port_desc = port_cls(
                                name=port.name,
                                direction=direction)
                            ports.append(port_desc)

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

