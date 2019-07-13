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

from noisicaa import node_db


CVMapperDescription = node_db.NodeDescription(
    uri='builtin://cv-mapper',
    display_name='Control Value Mapper (a-rate)',
    type=node_db.NodeDescription.PROCESSOR,
    node_ui=node_db.NodeUIDescription(
        type='builtin://cv-mapper',
    ),
    builtin_icon='node-type-builtin',
    processor=node_db.ProcessorDescription(
        type='builtin://cv-mapper',
    ),
    ports=[
        node_db.PortDescription(
            name='in',
            direction=node_db.PortDescription.INPUT,
            types=[node_db.PortDescription.ARATE_CONTROL],
        ),
        node_db.PortDescription(
            name='out',
            direction=node_db.PortDescription.OUTPUT,
            types=[node_db.PortDescription.ARATE_CONTROL],
        ),
    ]
)
