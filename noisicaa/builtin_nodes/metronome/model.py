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
import os.path
from typing import Any, Iterator

from noisicaa import constants
from noisicaa import audioproc
from noisicaa import node_db
from . import node_description
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class Metronome(_model.Metronome):
    def create(self, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.sample_path = os.path.join(constants.DATA_DIR, 'sounds', 'metronome.wav')

    def setup(self) -> None:
        super().setup()

        self.sample_path_changed.add(lambda _: self.update_spec())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_spec_mutation()

    def update_spec(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_spec_mutation())

    def __get_spec_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        spec = params.Extensions[processor_pb2.metronome_spec]
        spec.sample_path = self.sample_path
        spec.duration.numerator = 1
        spec.duration.denominator = 4

        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.MetronomeDescription)
        return node_desc
