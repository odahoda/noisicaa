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


MixerDescription = node_db.NodeDescription(
    uri='builtin://mixer',
    display_name='Mixer',
    type=node_db.NodeDescription.PROCESSOR,
    node_ui=node_db.NodeUIDescription(
        type='builtin://mixer',
    ),
    processor=node_db.ProcessorDescription(
        type='builtin://mixer',
    ),
    ports=[
        node_db.PortDescription(
            name='in:left',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.AUDIO,
        ),
        node_db.PortDescription(
            name='in:right',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.AUDIO,
        ),
        node_db.PortDescription(
            name='out:left',
            direction=node_db.PortDescription.OUTPUT,
            type=node_db.PortDescription.AUDIO,
        ),
        node_db.PortDescription(
            name='out:right',
            direction=node_db.PortDescription.OUTPUT,
            type=node_db.PortDescription.AUDIO,
        ),
        node_db.PortDescription(
            name='gain',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.KRATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                default=0.0,
                min=-50.0,
                max=20.0),
        ),
        node_db.PortDescription(
            name='pan',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.KRATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                default=0.0,
                min=-1.0,
                max=1.0),
        ),
        node_db.PortDescription(
            name='lp_cutoff',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.KRATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                default=20000.0,
                min=1.0,
                max=20000.0),
        ),
        node_db.PortDescription(
            name='hp_cutoff',
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.KRATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                default=1.0,
                min=1.0,
                max=20000.0),
        ),
    ]
)
