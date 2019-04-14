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
import typing
from typing import Any, Iterator, MutableSequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa.music import graph
from noisicaa.music import pmodel
from noisicaa.music import commands
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import model_pb2
from . import processor_pb2
from . import model

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class UpdateStepSequencer(commands.Command):
    proto_type = 'update_step_sequencer'
    proto_ext = commands_registry_pb2.update_step_sequencer

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateStepSequencer, self.pb)
        node = down_cast(StepSequencer, self.pool[pb.node_id])

        if pb.HasField('set_time_synched'):
            node.time_synched = pb.set_time_synched

        if pb.HasField('add_channel'):
            channel = self.pool.create(
                StepSequencerChannel,
                type=model_pb2.StepSequencerChannel.VALUE,
                num_steps=node.num_steps)
            node.channels.insert(pb.add_channel, channel)

        if pb.HasField('set_num_steps'):
            for channel in node.channels:
                while len(channel.steps) < pb.set_num_steps:
                    channel.steps.append(self.pool.create(StepSequencerStep))

            node.num_steps = pb.set_num_steps

            for channel in node.channels:
                while len(channel.steps) > pb.set_num_steps:
                    del channel.steps[len(channel.steps) - 1]


class UpdateStepSequencerChannel(commands.Command):
    proto_type = 'update_step_sequencer_channel'
    proto_ext = commands_registry_pb2.update_step_sequencer_channel

    def validate(self) -> None:
        pb = down_cast(commands_pb2.UpdateStepSequencerChannel, self.pb)
        channel = down_cast(StepSequencerChannel, self.pool[pb.channel_id])

        if pb.HasField('set_min_value') and channel.type != model_pb2.StepSequencerChannel.VALUE:
            raise ValueError(
                "Can't set min_value on %s channel"
                % model_pb2.StepSequencerChannel.Type.Name(channel.type))

        if pb.HasField('set_max_value') and channel.type != model_pb2.StepSequencerChannel.VALUE:
            raise ValueError(
                "Can't set max_value on %s channel"
                % model_pb2.StepSequencerChannel.Type.Name(channel.type))

        if pb.HasField('set_log_scale') and channel.type != model_pb2.StepSequencerChannel.VALUE:
            raise ValueError(
                "Can't set log_scale on %s channel"
                % model_pb2.StepSequencerChannel.Type.Name(channel.type))

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateStepSequencerChannel, self.pb)
        channel = down_cast(StepSequencerChannel, self.pool[pb.channel_id])

        if pb.HasField('set_type'):
            channel.type = pb.set_type

        if pb.HasField('set_min_value'):
            channel.min_value = pb.set_min_value

        if pb.HasField('set_max_value'):
            channel.max_value = pb.set_max_value

        if pb.HasField('set_log_scale'):
            channel.log_scale = pb.set_log_scale


class DeleteStepSequencerChannel(commands.Command):
    proto_type = 'delete_step_sequencer_channel'
    proto_ext = commands_registry_pb2.delete_step_sequencer_channel

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteStepSequencerChannel, self.pb)
        channel = down_cast(StepSequencerChannel, self.pool[pb.channel_id])
        node = down_cast(StepSequencer, channel.parent)

        del node.channels[channel.index]


class UpdateStepSequencerStep(commands.Command):
    proto_type = 'update_step_sequencer_step'
    proto_ext = commands_registry_pb2.update_step_sequencer_step

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateStepSequencerStep, self.pb)
        step = down_cast(StepSequencerStep, self.pool[pb.step_id])

        if pb.HasField('set_value'):
            step.value = pb.set_value

        if pb.HasField('set_enabled'):
            step.enabled = pb.set_enabled


class StepSequencerStep(model.StepSequencerStep, pmodel.ObjectBase):
    def setup(self) -> None:
        super().setup()

        self.enabled_changed.add(lambda _: self.sequencer.update_spec())
        self.value_changed.add(lambda _: self.sequencer.update_spec())

    @property
    def sequencer(self) -> 'StepSequencer':
        return down_cast(StepSequencer, self.parent.parent)

    @property
    def enabled(self) -> bool:
        return self.get_property_value('enabled')

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.set_property_value('enabled', value)

    @property
    def value(self) -> float:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: float) -> None:
        self.set_property_value('value', value)


class StepSequencerChannel(model.StepSequencerChannel, pmodel.ObjectBase):
    def create(
            self, *,
            type: model_pb2.StepSequencerChannel.Type = model_pb2.StepSequencerChannel.VALUE,  # pylint: disable=redefined-builtin
            num_steps: int = 8,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.type = type
        for _ in range(num_steps):
            self.steps.append(self._pool.create(StepSequencerStep))

    def setup(self) -> None:
        super().setup()

        self.type_changed.add(lambda _: self.sequencer.update_spec())
        self.min_value_changed.add(lambda _: self.sequencer.update_spec())
        self.max_value_changed.add(lambda _: self.sequencer.update_spec())

    @property
    def sequencer(self) -> 'StepSequencer':
        return down_cast(StepSequencer, self.parent)

    @property
    def type(self) -> model_pb2.StepSequencerChannel.Type:
        return self.get_property_value('type')

    @type.setter
    def type(self, value: model_pb2.StepSequencerChannel.Type) -> None:
        self.set_property_value('type', value)

    @property
    def steps(self) -> MutableSequence[StepSequencerStep]:
        return self.get_property_value('steps')

    @property
    def min_value(self) -> float:
        return self.get_property_value('min_value')

    @min_value.setter
    def min_value(self, value: float) -> None:
        self.set_property_value('min_value', value)

    @property
    def max_value(self) -> float:
        return self.get_property_value('max_value')

    @max_value.setter
    def max_value(self, value: float) -> None:
        self.set_property_value('max_value', value)

    @property
    def log_scale(self) -> bool:
        return self.get_property_value('log_scale')

    @log_scale.setter
    def log_scale(self, value: bool) -> None:
        self.set_property_value('log_scale', value)


class StepSequencer(model.StepSequencer, graph.BaseNode):
    def create(self, **kwargs: Any) -> None:
        super().create(**kwargs)

        channel = self._pool.create(
            StepSequencerChannel,
            type=model_pb2.StepSequencerChannel.VALUE,
            num_steps=self.num_steps)
        self.channels.append(channel)

    def setup(self) -> None:
        super().setup()

        self.channels_changed.add(lambda _: self.update_spec())
        self.time_synched_changed.add(lambda _: self.update_spec())
        self.num_steps_changed.add(lambda _: self.update_spec())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_spec_mutation()

    def update_spec(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_spec_mutation())

    def __get_spec_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        spec = params.Extensions[processor_pb2.step_sequencer_spec]
        spec.num_steps = self.num_steps
        spec.time_synched = self.time_synched
        for channel in self.channels:
            channel_spec = spec.channels.add()
            channel_spec.type = channel.type
            for step in channel.steps[:self.num_steps]:
                if channel.type in (model_pb2.StepSequencerChannel.GATE,
                                    model_pb2.StepSequencerChannel.TRIGGER):
                    channel_spec.step_enabled.append(step.enabled)
                else:
                    assert channel.type == model_pb2.StepSequencerChannel.VALUE
                    channel_spec.step_value.append(
                        step.value * (channel.max_value - channel.min_value) + channel.min_value)

        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    @property
    def channels(self) -> MutableSequence[StepSequencerChannel]:
        return self.get_property_value('channels')

    @property
    def time_synched(self) -> bool:
        return self.get_property_value('time_synched')

    @time_synched.setter
    def time_synched(self, value: bool) -> None:
        self.set_property_value('time_synched', value)

    @property
    def num_steps(self) -> int:
        return self.get_property_value('num_steps')

    @num_steps.setter
    def num_steps(self, value: int) -> None:
        self.set_property_value('num_steps', value)
