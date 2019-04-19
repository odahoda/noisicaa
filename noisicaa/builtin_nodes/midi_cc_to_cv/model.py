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

from typing import Any, Sequence

from noisicaa import core
from noisicaa import node_db
from noisicaa import model
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description
from . import model_pb2


class MidiCCtoCVChannel(model.ProjectChild):
    class MidiCCtoCVChannelSpec(model.ObjectSpec):
        proto_type = 'midi_cc_to_cv_channel'
        proto_ext = model_registry_pb2.midi_cc_to_cv_channel

        type = model.Property(model_pb2.MidiCCtoCVChannel.Type)
        midi_channel = model.Property(int, default=0)
        midi_controller = model.Property(int, default=0)
        min_value = model.Property(float, default=0.0)
        max_value = model.Property(float, default=1.0)
        log_scale = model.Property(bool, default=False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.type_changed = core.Callback[model.PropertyChange[int]]()
        self.midi_channel_changed = core.Callback[model.PropertyChange[int]]()
        self.midi_controller_changed = core.Callback[model.PropertyChange[int]]()
        self.min_value_changed = core.Callback[model.PropertyChange[float]]()
        self.max_value_changed = core.Callback[model.PropertyChange[float]]()
        self.log_scale_changed = core.Callback[model.PropertyChange[bool]]()

    @property
    def type(self) -> model_pb2.MidiCCtoCVChannel.Type:
        return self.get_property_value('type')

    @property
    def midi_channel(self) -> int:
        return self.get_property_value('midi_channel')

    @property
    def midi_controller(self) -> float:
        return self.get_property_value('midi_controller')

    @property
    def min_value(self) -> float:
        return self.get_property_value('min_value')

    @property
    def max_value(self) -> float:
        return self.get_property_value('max_value')

    @property
    def log_scale(self) -> bool:
        return self.get_property_value('log_scale')


class MidiCCtoCV(model.BaseNode):
    class MidiCCtoCVSpec(model.ObjectSpec):
        proto_type = 'midi_cc_to_cv'
        proto_ext = model_registry_pb2.midi_cc_to_cv

        channels = model.ObjectListProperty(MidiCCtoCVChannel)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.channels_changed = core.Callback[model.PropertyListChange[MidiCCtoCVChannel]]()

    def setup(self) -> None:
        super().setup()

        self.channels_changed.add(self.description_changed.call)

    @property
    def channels(self) -> Sequence[MidiCCtoCVChannel]:
        return self.get_property_value('channels')

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.MidiCCtoCVDescription)

        for idx in range(len(self.channels)):
            node_desc.ports.add(
                name='channel%d' % (idx + 1),
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.ARATE_CONTROL,
            )

        return node_desc
