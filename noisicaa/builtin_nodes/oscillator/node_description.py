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


OscillatorDescription = node_db.NodeDescription(
    uri='builtin://oscillator',
    display_name='Oscillator',
    type=node_db.NodeDescription.PROCESSOR,
    node_ui=node_db.NodeUIDescription(
        type='builtin://generic',
    ),
    builtin_icon='node-type-builtin',
    processor=node_db.ProcessorDescription(
        type='builtin://oscillator',
    ),
    ports=[
        node_db.PortDescription(
            name='waveform',
            display_name="Waveform",
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.ARATE_CONTROL,
            enum_value=node_db.EnumValueDescription(
                default=0.0,
                items=[
                    node_db.EnumValueItem(
                        name="Sine",
                        value=0.0),
                    node_db.EnumValueItem(
                        name="Sawtooth",
                        value=1.0),
                    node_db.EnumValueItem(
                        name="Square",
                        value=2.0),
                ]),
        ),
        node_db.PortDescription(
            name='freq',
            display_name="Frequency (Hz)",
            direction=node_db.PortDescription.INPUT,
            type=node_db.PortDescription.ARATE_CONTROL,
            float_value=node_db.FloatValueDescription(
                default=440.0,
                min=1.0,
                max=20000.0,
                scale=node_db.FloatValueDescription.LOG),
        ),
        node_db.PortDescription(
            name='out',
            direction=node_db.PortDescription.OUTPUT,
            type=node_db.PortDescription.AUDIO,
        ),
    ]
)
