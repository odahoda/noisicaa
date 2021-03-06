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

from noisicaa import audioproc
from noisicaa import music
from noisicaa import node_db
from . import node_description
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class MidiVelocityMapper(_model.MidiVelocityMapper):
    def create(self, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.transfer_function = self._pool.create(
            music.TransferFunction,
            input_min=0.0,
            input_max=127.0,
            output_min=0.0,
            output_max=127.0,
            type=music.TransferFunction.FIXED,
            fixed_value=100.0,
            linear_left_value=0.0,
            linear_right_value=127.0)

    def setup(self) -> None:
        super().setup()

        self.transfer_function.object_changed.add(lambda _: self.update_spec())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_spec_mutation()

    def update_spec(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_spec_mutation())

    def __get_spec_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        spec = params.Extensions[processor_pb2.midi_velocity_mapper_spec]
        spec.transfer_function.CopyFrom(self.transfer_function.get_function_spec())

        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.MidiVelocityMapperDescription)
        return node_desc
