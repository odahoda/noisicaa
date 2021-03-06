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
from typing import Iterator

from noisicaa import node_db
from noisicaa.builtin_nodes import node_description_registry

from . import scanner

logger = logging.getLogger(__name__)


class Builtins(object):
    RealmSinkDescription = node_db.NodeDescription(
        uri='builtin://sink',
        display_name='Output',
        internal=True,
        type=node_db.NodeDescription.REALM_SINK,
        node_ui=node_db.NodeUIDescription(
            type='builtin://no-ui',
            muteable=False,
        ),
        ports=[
            node_db.PortDescription(
                name='in:left',
                direction=node_db.PortDescription.INPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
            node_db.PortDescription(
                name='in:right',
                direction=node_db.PortDescription.INPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
        ]
    )

    ChildRealmDescription = node_db.NodeDescription(
        uri='builtin://child_realm',
        display_name='Child',
        internal=True,
        type=node_db.NodeDescription.CHILD_REALM,
        ports=[
            node_db.PortDescription(
                name='in:events',
                direction=node_db.PortDescription.INPUT,
                types=[node_db.PortDescription.EVENTS],
            ),
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
        ]
    )

    SoundFileDescription = node_db.NodeDescription(
        uri='builtin://sound_file',
        display_name='Sound Player',
        internal=True,
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type='builtin://sound-file',
        ),
        ports=[
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                types=[node_db.PortDescription.AUDIO],
            ),
        ]
    )


class BuiltinScanner(scanner.Scanner):
    def scan(self) -> Iterator[node_db.NodeDescription]:
        yield Builtins.RealmSinkDescription
        yield Builtins.ChildRealmDescription
        yield Builtins.SoundFileDescription

        yield from node_description_registry.node_descriptions()
