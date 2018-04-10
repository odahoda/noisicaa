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
from typing import Iterator, Tuple

from noisicaa import node_db
from noisicaa import lv2
from noisicaa.bindings import lilv

from . import scanner

logger = logging.getLogger(__name__)

supported_uis = {
    'http://lv2plug.in/ns/extensions/ui#Gtk3UI',
    'http://lv2plug.in/ns/extensions/ui#GtkUI',
    'http://lv2plug.in/ns/extensions/ui#Qt4UI',
    'http://lv2plug.in/ns/extensions/ui#Qt5UI',
    'http://lv2plug.in/ns/extensions/ui#X11UI',
}


class LV2Scanner(scanner.Scanner):
    def scan(self) -> Iterator[Tuple[str, node_db.NodeDescription]]:
        world = lilv.World()
        ns = world.ns
        world.load_all()

        plugins = world.get_all_plugins()

        for plugin in plugins:
            logger.info("Adding LV2 plugin %s", plugin.get_uri())

            desc = node_db.NodeDescription()
            desc.supported = True
            desc.type = node_db.NodeDescription.PLUGIN
            desc.processor.type = node_db.ProcessorDescription.PLUGIN
            desc.plugin.type = node_db.PluginDescription.LV2
            desc.display_name = str(plugin.get_name())

            lv2_desc = desc.lv2
            lv2_desc.uri = str(plugin.get_uri())

            for uri in plugin.required_features:
                feature_desc = lv2_desc.features.add()
                feature_desc.required = True
                feature_desc.uri = uri
                if not lv2.supports_plugin_feature(uri):
                    desc.supported = False
                    desc.not_supported_reasons.unsupported_lv2_feature.append(uri)

            for feature_uri in plugin.optional_features:
                feature_desc = lv2_desc.features.add()
                feature_desc.required = False
                feature_desc.uri = feature_uri

            for ui in plugin.get_uis():
                ui_desc = lv2_desc.uis.add()
                ui_desc.supported = True
                ui_desc.uri = ui.uri

                for cl in ui.get_classes():
                    if str(cl) in supported_uis:
                        ui_desc.type_uri = str(cl)

                if not ui_desc.type_uri:
                    ui_desc.supported = False
                    for cl in ui.get_classes():
                        ui_desc.not_supported_reasons.unsupported_lv2_ui_type.append(str(cl))

                for uri in ui.required_features:
                    feature_desc = ui_desc.features.add()
                    feature_desc.required = True
                    feature_desc.uri = uri
                    if not lv2.supports_ui_feature(uri):
                        ui_desc.supported = False
                        ui_desc.not_supported_reasons.unsupported_lv2_feature.append(uri)

                for feature_uri in ui.optional_features:
                    feature_desc = ui_desc.features.add()
                    feature_desc.required = False
                    feature_desc.uri = feature_uri

                if ui_desc.supported:
                    ui_desc.bundle_path = ui.bundle_path
                    ui_desc.binary_path = ui.binary_path
                    if not lv2_desc.ui_uri:
                        lv2_desc.ui_uri = ui.uri

            desc.has_ui = bool(lv2_desc.ui_uri)

            for port in (plugin.get_port_by_index(i) for i in range(plugin.get_num_ports())):
                port_desc = desc.ports.add()
                port_desc.name = str(port.get_symbol())
                port_desc.display_name = str(port.get_name())

                if port.is_a(ns.lv2.InputPort):
                    port_desc.direction = node_db.PortDescription.INPUT
                elif port.is_a(ns.lv2.OutputPort):
                    port_desc.direction = node_db.PortDescription.OUTPUT
                else:
                    raise ValueError(port)

                if port.is_a(ns.lv2.ControlPort):
                    port_desc.type = node_db.PortDescription.KRATE_CONTROL
                elif port.is_a(ns.lv2.AudioPort):
                    port_desc.type = node_db.PortDescription.AUDIO
                elif port.is_a(ns.atom.AtomPort):
                    port_desc.type = node_db.PortDescription.EVENTS
                else:
                    port_desc.type = node_db.PortDescription.UNSUPPORTED

                if port.is_a(ns.lv2.ControlPort):
                #     # if port.has_property(ns.lv2.integer):
                #     #     # TODO: this should be IntParameter
                #     #     parameter_cls = node_db.FloatParameterDescription
                #     # else:
                #     #     parameter_cls = node_db.FloatParameterDescription

                    value_desc = port_desc.float_value
                    default, range_min, range_max = port.get_range()
                    if default is not None:
                        if default.is_int():
                            value_desc.default = int(default)
                        else:
                            value_desc.default = float(default)
                    if range_min is not None:
                        if range_min.is_int():
                            value_desc.min = int(range_min)
                        else:
                            value_desc.min = float(range_min)
                    if range_max is not None:
                        if range_max.is_int():
                            value_desc.max = int(range_max)
                        else:
                            value_desc.max = float(range_max)

            if not desc.supported:
                # TODO: also add unsupported plugins to DB.
                logger.warning(
                    "Not adding LV2 plugin %s:\n%s",
                    plugin.get_uri(),
                    desc.not_supported_reasons)
                continue

            yield str(plugin.get_uri()), desc
