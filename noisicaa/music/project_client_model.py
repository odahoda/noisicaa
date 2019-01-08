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

from typing import Any, Sequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import node_db as node_db_lib


class ObjectBase(model.ObjectBase):  # pylint: disable=abstract-method
    pass


class ProjectChild(model.ProjectChild, ObjectBase):
    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)


class PipelineGraphControlValue(ProjectChild, model.PipelineGraphControlValue, ObjectBase):
    pass


class BasePipelineGraphNode(ProjectChild, model.BasePipelineGraphNode, ObjectBase):  # pylint: disable=abstract-method
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def graph_pos(self) -> model.Pos2F:
        return self.get_property_value('graph_pos')

    @property
    def graph_size(self) -> model.SizeF:
        return self.get_property_value('graph_size')

    @property
    def graph_color(self) -> model.Color:
        return self.get_property_value('graph_color')

    @property
    def plugin_state(self) -> audioproc.PluginState:
        return self.get_property_value('plugin_state')



class PipelineGraphNode(BasePipelineGraphNode, model.PipelineGraphNode, ObjectBase):
    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')


class AudioOutPipelineGraphNode(
        BasePipelineGraphNode, model.AudioOutPipelineGraphNode, ObjectBase):
    pass


class Track(BasePipelineGraphNode, model.Track, ObjectBase):  # pylint: disable=abstract-method
    @property
    def visible(self) -> bool:
        return self.get_property_value('visible')

    @property
    def list_position(self) -> int:
        return self.get_property_value('list_position')


class Measure(ProjectChild, model.Measure, ObjectBase):
    @property
    def time_signature(self) -> model.TimeSignature:
        return self.get_property_value('time_signature')


class MeasureReference(ProjectChild, model.MeasureReference, ObjectBase):
    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')


class MeasuredTrack(Track, model.MeasuredTrack, ObjectBase):  # pylint: disable=abstract-method
    @property
    def measure_list(self) -> Sequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def measure_heap(self) -> Sequence[Measure]:
        return self.get_property_value('measure_heap')


class PipelineGraphConnection(ProjectChild, model.PipelineGraphConnection, ObjectBase):
    @property
    def source_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('source_node')

    @property
    def source_port(self) -> str:
        return self.get_property_value('source_port')

    @property
    def dest_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('dest_node')

    @property
    def dest_port(self) -> str:
        return self.get_property_value('dest_port')


class Sample(ProjectChild, model.Sample, ObjectBase):
    @property
    def path(self) -> str:
        return self.get_property_value('path')


class Metadata(ProjectChild, model.Metadata, ObjectBase):
    @property
    def author(self) -> str:
        return self.get_property_value('author')

    @property
    def license(self) -> str:
        return self.get_property_value('license')

    @property
    def copyright(self) -> str:
        return self.get_property_value('copyright')

    @property
    def created(self) -> int:
        return self.get_property_value('created')


class Project(model.Project, ObjectBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_db = None  # type: node_db_lib.NodeDBClient
        self.__time_mapper = None  # type: audioproc.TimeMapper

    @property
    def metadata(self) -> Metadata:
        return self.get_property_value('metadata')

    @property
    def pipeline_graph_nodes(self) -> Sequence[BasePipelineGraphNode]:
        return self.get_property_value('pipeline_graph_nodes')

    @property
    def pipeline_graph_connections(self) -> Sequence[PipelineGraphConnection]:
        return self.get_property_value('pipeline_graph_connections')

    @property
    def samples(self) -> Sequence[Sample]:
        return self.get_property_value('samples')

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    @property
    def time_mapper(self) -> audioproc.TimeMapper:
        return self.__time_mapper

    def init(self, node_db: node_db_lib.NodeDBClient) -> None:
        self.__node_db = node_db

        # TODO: use correct sample_rate
        self.__time_mapper = audioproc.TimeMapper(44100)
        self.__time_mapper.setup(self)

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.__node_db.get_node_description(uri)
