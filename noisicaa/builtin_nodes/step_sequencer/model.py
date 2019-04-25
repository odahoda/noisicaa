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


class StepSequencerStep(model.ProjectChild):
    class StepSequencerStepSpec(model.ObjectSpec):
        proto_type = 'step_sequencer_step'
        proto_ext = model_registry_pb2.step_sequencer_step

        enabled = model.Property(bool, default=False)
        value = model.Property(float, default=0.0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.enabled_changed = core.Callback[model.PropertyChange[bool]]()
        self.value_changed = core.Callback[model.PropertyChange[float]]()

    @property
    def enabled(self) -> bool:
        return self.get_property_value('enabled')

    @property
    def value(self) -> float:
        return self.get_property_value('value')


class StepSequencerChannel(model.ProjectChild):
    class StepSequencerChannelSpec(model.ObjectSpec):
        proto_type = 'step_sequencer_channel'
        proto_ext = model_registry_pb2.step_sequencer_channel

        type = model.Property(model_pb2.StepSequencerChannel.Type)
        steps = model.ObjectListProperty(StepSequencerStep)
        min_value = model.Property(float, default=0.0)
        max_value = model.Property(float, default=1.0)
        log_scale = model.Property(bool, default=False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.type_changed = core.Callback[model.PropertyChange[int]]()
        self.steps_changed = core.Callback[model.PropertyListChange[StepSequencerStep]]()
        self.min_value_changed = core.Callback[model.PropertyChange[float]]()
        self.max_value_changed = core.Callback[model.PropertyChange[float]]()
        self.log_scale_changed = core.Callback[model.PropertyChange[bool]]()

    @property
    def type(self) -> model_pb2.StepSequencerChannel.Type:
        return self.get_property_value('type')

    @property
    def steps(self) -> Sequence[StepSequencerStep]:
        return self.get_property_value('steps')

    @property
    def min_value(self) -> float:
        return self.get_property_value('min_value')

    @property
    def max_value(self) -> float:
        return self.get_property_value('max_value')

    @property
    def log_scale(self) -> bool:
        return self.get_property_value('log_scale')


class StepSequencer(model.BaseNode):
    class StepSequencerSpec(model.ObjectSpec):
        proto_type = 'step_sequencer'
        proto_ext = model_registry_pb2.step_sequencer

        channels = model.ObjectListProperty(StepSequencerChannel)
        time_synched = model.Property(bool, default=False)
        num_steps = model.Property(int, default=8)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.channels_changed = core.Callback[model.PropertyListChange[StepSequencerChannel]]()
        self.time_synched_changed = core.Callback[model.PropertyChange[bool]]()
        self.num_steps_changed = core.Callback[model.PropertyChange[int]]()

    def setup(self) -> None:
        super().setup()

        self.channels_changed.add(self.description_changed.call)

    @property
    def channels(self) -> Sequence[StepSequencerChannel]:
        return self.get_property_value('channels')

    @property
    def time_synched(self) -> bool:
        return self.get_property_value('time_synched')

    @property
    def num_steps(self) -> int:
        return self.get_property_value('num_steps')

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.StepSequencerDescription)

        for idx in range(len(self.channels)):
            node_desc.ports.add(
                name='channel%d' % (idx + 1),
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.ARATE_CONTROL,
            )

        return node_desc
