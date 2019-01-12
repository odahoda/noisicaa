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

from typing import Optional, Iterator, MutableSequence, Callable

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import model

# All of these classes are abstract.
# pylint: disable=abstract-method


class ObjectBase(model.ObjectBase):
    _pool = None  # type: Pool

    def property_changed(self, change: model.PropertyChange) -> None:
        super().property_changed(change)
        self._pool.model_changed.call(change)


class ProjectChild(model.ProjectChild, ObjectBase):
    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)


class NodeConnector(object):
    pass


class PipelineGraphControlValue(ProjectChild, model.PipelineGraphControlValue, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def value(self) -> model.ControlValue:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: model.ControlValue) -> None:
        self.set_property_value('value', value)


class BasePipelineGraphNode(ProjectChild, model.BasePipelineGraphNode, ObjectBase):
    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def graph_pos(self) -> model.Pos2F:
        return self.get_property_value('graph_pos')

    @graph_pos.setter
    def graph_pos(self, value: model.Pos2F) -> None:
        self.set_property_value('graph_pos', value)

    @property
    def graph_size(self) -> model.SizeF:
        return self.get_property_value('graph_size')

    @graph_size.setter
    def graph_size(self, value: model.SizeF) -> None:
        self.set_property_value('graph_size', value)

    @property
    def graph_color(self) -> model.Color:
        return self.get_property_value('graph_color')

    @graph_color.setter
    def graph_color(self, value: model.Color) -> None:
        self.set_property_value('graph_color', value)

    @property
    def control_values(self) -> MutableSequence[PipelineGraphControlValue]:
        return self.get_property_value('control_values')

    @property
    def plugin_state(self) -> audioproc.PluginState:
        return self.get_property_value('plugin_state')

    @plugin_state.setter
    def plugin_state(self, value: audioproc.PluginState) -> None:
        self.set_property_value('plugin_state', value)

    @property
    def pipeline_node_id(self) -> str:
        raise NotImplementedError

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def set_control_value(self, port_name: str, value: float, generation: int) -> None:
        raise NotImplementedError

    def set_plugin_state(self, plugin_state: audioproc.PluginState) -> None:
        raise NotImplementedError

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]) -> NodeConnector:
        raise NotImplementedError



class PipelineGraphNode(BasePipelineGraphNode, model.PipelineGraphNode, ObjectBase):
    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @node_uri.setter
    def node_uri(self, value: str) -> None:
        self.set_property_value('node_uri', value)

    def to_preset(self) -> bytes:
        raise NotImplementedError

    def from_preset(self, xml: bytes) -> None:
        raise NotImplementedError


class AudioOutPipelineGraphNode(
        BasePipelineGraphNode, model.AudioOutPipelineGraphNode, ObjectBase):
    pass


class Track(BasePipelineGraphNode, model.Track, ObjectBase):
    @property
    def visible(self) -> bool:
        return self.get_property_value('visible')

    @visible.setter
    def visible(self, value: bool) -> None:
        self.set_property_value('visible', value)

    @property
    def list_position(self) -> int:
        return self.get_property_value('list_position')

    @list_position.setter
    def list_position(self, value: int) -> None:
        self.set_property_value('list_position', value)


class Measure(ProjectChild, model.Measure, ObjectBase):
    @property
    def time_signature(self) -> model.TimeSignature:
        return self.get_property_value('time_signature')

    @time_signature.setter
    def time_signature(self, value: model.TimeSignature) -> None:
        self.set_property_value('time_signature', value)


class MeasureReference(ProjectChild, model.MeasureReference, ObjectBase):
    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')

    @measure.setter
    def measure(self, value: Measure) -> None:
        self.set_property_value('measure', value)


class MeasuredTrack(Track, model.MeasuredTrack, ObjectBase):
    @property
    def measure_list(self) -> MutableSequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def measure_heap(self) -> MutableSequence[Measure]:
        return self.get_property_value('measure_heap')

    def append_measure(self) -> None:
        raise NotImplementedError

    def insert_measure(self, idx: int) -> None:
        raise NotImplementedError

    def remove_measure(self, idx: int) -> None:
        raise NotImplementedError

    def create_empty_measure(self, ref: Optional[Measure]) -> Measure:
        raise NotImplementedError

    def garbage_collect_measures(self) -> None:
        raise NotImplementedError


class PipelineGraphConnection(ProjectChild, model.PipelineGraphConnection, ObjectBase):
    @property
    def source_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('source_node')

    @source_node.setter
    def source_node(self, value: BasePipelineGraphNode) -> None:
        self.set_property_value('source_node', value)

    @property
    def source_port(self) -> str:
        return self.get_property_value('source_port')

    @source_port.setter
    def source_port(self, value: str) -> None:
        self.set_property_value('source_port', value)

    @property
    def dest_node(self) -> BasePipelineGraphNode:
        return self.get_property_value('dest_node')

    @dest_node.setter
    def dest_node(self, value: BasePipelineGraphNode) -> None:
        self.set_property_value('dest_node', value)

    @property
    def dest_port(self) -> str:
        return self.get_property_value('dest_port')

    @dest_port.setter
    def dest_port(self, value: str) -> None:
        self.set_property_value('dest_port', value)

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError


class Sample(ProjectChild, model.Sample, ObjectBase):
    @property
    def path(self) -> str:
        return self.get_property_value('path')

    @path.setter
    def path(self, value: str) -> None:
        self.set_property_value('path', value)


class Metadata(ProjectChild, model.Metadata, ObjectBase):
    @property
    def author(self) -> str:
        return self.get_property_value('author')

    @author.setter
    def author(self, value: str) -> None:
        self.set_property_value('author', value)

    @property
    def license(self) -> str:
        return self.get_property_value('license')

    @license.setter
    def license(self, value: str) -> None:
        self.set_property_value('license', value)

    @property
    def copyright(self) -> str:
        return self.get_property_value('copyright')

    @copyright.setter
    def copyright(self, value: str) -> None:
        self.set_property_value('copyright', value)

    @property
    def created(self) -> int:
        return self.get_property_value('created')

    @created.setter
    def created(self, value: int) -> None:
        self.set_property_value('created', value)


class Project(model.Project, ObjectBase):
    @property
    def metadata(self) -> Metadata:
        return self.get_property_value('metadata')

    @metadata.setter
    def metadata(self, value: Metadata) -> None:
        self.set_property_value('metadata', value)

    @property
    def pipeline_graph_nodes(self) -> MutableSequence[BasePipelineGraphNode]:
        return self.get_property_value('pipeline_graph_nodes')

    @property
    def pipeline_graph_connections(self) -> MutableSequence[PipelineGraphConnection]:
        return self.get_property_value('pipeline_graph_connections')

    @property
    def samples(self) -> MutableSequence[Sample]:
        return self.get_property_value('samples')

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @bpm.setter
    def bpm(self, value: int) -> None:
        self.set_property_value('bpm', value)

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        raise NotImplementedError  # pragma: no coverage

    @property
    def audio_out_node(self) -> AudioOutPipelineGraphNode:
        return down_cast(AudioOutPipelineGraphNode, super().audio_out_node)

    def add_pipeline_graph_node(self, node: BasePipelineGraphNode) -> None:
        raise NotImplementedError  # pragma: no coverage

    def remove_pipeline_graph_node(self, node: BasePipelineGraphNode) -> None:
        raise NotImplementedError  # pragma: no coverage

    def add_pipeline_graph_connection(self, connection: PipelineGraphConnection) -> None:
        raise NotImplementedError  # pragma: no coverage

    def remove_pipeline_graph_connection(self, connection: PipelineGraphConnection) -> None:
        raise NotImplementedError  # pragma: no coverage

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError  # pragma: no coverage

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        raise NotImplementedError  # pragma: no coverage


class Pool(model.Pool[ObjectBase]):
    def __init__(self) -> None:
        super().__init__()

        self.model_changed = core.Callback[model.Mutation]()

    def object_added(self, obj: model.ObjectBase) -> None:
        self.model_changed.call(model.ObjectAdded(obj))

    def object_removed(self, obj: model.ObjectBase) -> None:
        self.model_changed.call(model.ObjectRemoved(obj))
