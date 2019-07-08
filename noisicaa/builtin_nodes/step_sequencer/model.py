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
from typing import Any, Iterator

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import node_db
from . import node_description
from . import model_pb2
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class StepSequencerStep(_model.StepSequencerStep):
    def setup(self) -> None:
        super().setup()

        self.enabled_changed.add(lambda _: self.sequencer.update_spec())
        self.value_changed.add(lambda _: self.sequencer.update_spec())

    @property
    def sequencer(self) -> 'StepSequencer':
        return down_cast(StepSequencer, self.parent.parent)


class StepSequencerChannel(_model.StepSequencerChannel):
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


class StepSequencer(_model.StepSequencer):
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

        self.channels_changed.add(self.description_changed.call)

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
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.StepSequencerDescription)

        for idx in range(len(self.channels)):
            node_desc.ports.add(
                name='channel%d' % (idx + 1),
                direction=node_db.PortDescription.OUTPUT,
                types=[node_db.PortDescription.ARATE_CONTROL],
            )

        return node_desc

    def create_channel(self, index: int) -> StepSequencerChannel:
        channel = self._pool.create(
            StepSequencerChannel,
            type=model_pb2.StepSequencerChannel.VALUE,
            num_steps=self.num_steps)
        self.channels.insert(index, channel)
        return channel

    def delete_channel(self, channel: StepSequencerChannel) -> None:
        del self.channels[channel.index]

    def set_num_steps(self, num_steps: int) -> None:
        for channel in self.channels:
            while len(channel.steps) < num_steps:
                channel.steps.append(self._pool.create(StepSequencerStep))

        self.num_steps = num_steps

        for channel in self.channels:
            while len(channel.steps) > num_steps:
                del channel.steps[len(channel.steps) - 1]
