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


StepSequencerDescription = node_db.NodeDescription(
    uri='builtin://step-sequencer',
    display_name='Step Sequencer',
    type=node_db.NodeDescription.PROCESSOR,
    node_ui=node_db.NodeUIDescription(
        type='builtin://step-sequencer',
    ),
    builtin_icon='node-type-builtin',
    processor=node_db.ProcessorDescription(
        type='builtin://step-sequencer',
    ),
    ports=[
        node_db.PortDescription(
            name='tempo',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.ARATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                min=0.01,
                max=100.0,
                default=8,
                scale=node_db.FloatValueDescription.LOG),
        ),
    ]
)
