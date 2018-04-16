#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

from typing import Any, Iterator

from noisicaa import audioproc
from noisicaa import node_db as node_db_lib

from . import model
from . import commands
from . import state as state_lib
from . import mutations


class IProject(model.Project, state_lib.RootMixin, state_lib.StateBase):
    @property
    def duration(self) -> audioproc.MusicalDuration:
        raise NotImplementedError

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        raise NotImplementedError

    def dispatch_command(self, obj_id: str, cmd: commands.Command) -> Any:
        raise NotImplementedError

    def equalize_tracks(self, remove_trailing_empty_measures: int = 0) -> None:
        raise NotImplementedError

    def handle_pipeline_mutation(self, mutation: mutations.Mutation) -> None:
        raise NotImplementedError

    @property
    def audio_out_node(self) -> model.BasePipelineGraphNode:
        raise NotImplementedError

    def add_pipeline_graph_node(self, node: model.BasePipelineGraphNode) -> None:
        raise NotImplementedError

    def remove_pipeline_graph_node(self, node: model.BasePipelineGraphNode) -> None:
        raise NotImplementedError

    def add_pipeline_graph_connection(
            self, connection: model.PipelineGraphConnection) -> None:
        raise NotImplementedError

    def remove_pipeline_graph_connection(
            self, connection: model.PipelineGraphConnection) -> None:
        raise NotImplementedError

    def get_add_mutations(self) -> Iterator[mutations.Mutation]:
        raise NotImplementedError

    def get_remove_mutations(self) -> Iterator[mutations.Mutation]:
        raise NotImplementedError
