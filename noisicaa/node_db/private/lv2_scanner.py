#!/usr/bin/python3

import logging
import os
import os.path

from noisicaa.bindings import lilv
from noisicaa import constants
from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class LV2Scanner(scanner.Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def scan(self):
        world = lilv.World()
        ns = world.ns
        world.load_all()

        plugins = world.get_all_plugins()

        for plugin in plugins:
            missing_features = plugin.get_missing_features()
            if missing_features:
                logger.warning(
                    "Not adding LV2 plugin %s, because it requires unsupported features %s",
                    plugin.get_uri(), ", ".join(missing_features))
                continue

            logger.info("Adding LV2 plugin %s", plugin.get_uri())

            ports = []
            parameters = []

            for port in (plugin.get_port_by_index(i) for i in range(plugin.get_num_ports())):
                if port.is_a(ns.lv2.ControlPort) and port.is_a(ns.lv2.InputPort):
                    if port.has_property(ns.lv2.integer):
                        # TODO: this should be IntParameter
                        parameter_cls = node_db.FloatParameterDescription
                    else:
                        parameter_cls = node_db.FloatParameterDescription

                    kwargs = {}
                    kwargs['name'] = str(port.get_symbol())
                    kwargs['display_name'] = str(port.get_name())

                    default, range_min, range_max = port.get_range()
                    if default is not None:
                        if default.is_int():
                            kwargs['default'] = int(default)
                        else:
                            kwargs['default'] = float(default)
                    if range_min is not None:
                        if range_min.is_int():
                            kwargs['min'] = int(range_min)
                        else:
                            kwargs['min'] = float(range_min)
                    if range_max is not None:
                        if range_max.is_int():
                            kwargs['max'] = int(range_max)
                        else:
                            kwargs['max'] = float(range_max)

                    parameter_desc = parameter_cls(**kwargs)
                    parameters.append(parameter_desc)

                elif port.is_a(ns.lv2.AudioPort):
                    if port.is_a(ns.lv2.InputPort):
                        direction = node_db.PortDirection.Input
                    elif port.is_a(ns.lv2.OutputPort):
                        direction = node_db.PortDirection.Output
                    else:
                        raise ValueError(port)

                    kwargs = {}
                    kwargs['channels'] = 'mono'

                    port_desc = node_db.AudioPortDescription(
                        name=str(port.get_symbol()),
                        direction=direction,
                        **kwargs)
                    ports.append(port_desc)
                else:
                    # TODO: support other port types (atom, control output, ...).
                    logger.warn(
                        "Ignoring unsupported port %s (%s)",
                        port.get_symbol(), ', '.join(str(cls) for cls in port.get_classes()))

            parameters.append(
                node_db.InternalParameterDescription(
                    name='uri', value=str(plugin.get_uri())))

            node_desc = node_db.UserNodeDescription(
                display_name=str(plugin.get_name()),
                node_cls='lv2',
                ports=ports,
                parameters=parameters)

            yield str(plugin.get_uri()), node_desc
