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
from typing import Iterator, Dict

from noisicaa import node_db

from . import csound_scanner
from . import builtin_scanner
from . import ladspa_scanner
from . import lv2_scanner
#from . import preset_scanner

logger = logging.getLogger(__name__)


class NodeDB(object):
    def __init__(self) -> None:
        self.__nodes = {}  # type: Dict[str, node_db.NodeDescription]

    def __getitem__(self, uri: str) -> node_db.NodeDescription:
        return self.get_node_description(uri)

    def get_node_description(self, uri: str) -> node_db.NodeDescription:
        desc = node_db.NodeDescription()
        desc.CopyFrom(self.__nodes[uri])
        return desc

    def setup(self) -> None:
        scanners = [
            csound_scanner.CSoundScanner(),
            builtin_scanner.BuiltinScanner(),
            ladspa_scanner.LadspaScanner(),
            lv2_scanner.LV2Scanner(),
        ]
        for scanner in scanners:
            for uri, node_description in scanner.scan():
                logger.debug("%s:\n%s", uri, node_description)
                assert uri not in self.__nodes
                self.__nodes[uri] = node_description

        # scanner = preset_scanner.PresetScanner(self.__nodes)
        # presets = {}
        # for uri, preset_description in scanner.scan():
        #     assert uri not in presets
        #     presets[uri] = preset_description
        # self.__nodes.update(presets)

    def cleanup(self) -> None:
        pass

    def initial_mutations(self) -> Iterator[node_db.Mutation]:
        for uri, node_description in sorted(self.__nodes.items()):
            yield node_db.AddNodeDescription(uri, node_description)

    def start_scan(self) -> None:
        pass
