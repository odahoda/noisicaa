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

import functools
import logging
from typing import cast, Any, Dict, Set, Sequence, List

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from . import time_signature as time_signature_lib
from . import pos2f
from . import sizef
from . import color
from . import model_base
from . import project_pb2

logger = logging.getLogger(__name__)


class ObjectBase(model_base.ObjectBase):
    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        callback = getattr(self, change.prop_name + '_changed')
        callback.call(change)

    @property
    def parent(self) -> 'ObjectBase':
        return cast(ObjectBase, super().parent)

    @property
    def project(self) -> 'Project':
        return cast(Project, self._pool.root)

    @property
    def attached_to_project(self) -> bool:
        raise NotImplementedError


class ProjectChild(ObjectBase):
    @property
    def attached_to_project(self) -> bool:
        if not self.is_attached:
            return None
        return self.parent.attached_to_project


class Sample(ProjectChild):
    class SampleSpec(model_base.ObjectSpec):
        proto_type = 'sample'
        proto_ext = project_pb2.sample  # type: ignore

        path = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.path_changed = core.Callback[model_base.PropertyChange[str]]()


class PipelineGraphControlValue(ProjectChild):
    class PipelineGraphControlValueSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_control_value'
        proto_ext = project_pb2.pipeline_graph_control_value  # type: ignore

        name = model_base.Property(str)
        value = model_base.ProtoProperty(project_pb2.ControlValue)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.value_changed = core.Callback[model_base.PropertyChange[project_pb2.ControlValue]]()

    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @property
    def value(self) -> project_pb2.ControlValue:
        return self.get_property_value('value')


class ControlValueMap(object):
    def __init__(self, node: 'BasePipelineGraphNode') -> None:
        self.__node = node

        self.__initialized = False
        self.__control_values = {}  # type: Dict[str, project_pb2.ControlValue]
        self.__control_value_listeners = []  # type: List[core.Listener]
        self.__control_values_listener = None # type: core.Listener

        self.control_value_changed = core.CallbackMap[str, model_base.PropertyValueChange]()

    def value(self, name: str) -> float:
        return self.__control_values[name].value

    def generation(self, name: str) -> int:
        return self.__control_values[name].generation

    def init(self) -> None:
        if self.__initialized:
            return

        for port in self.__node.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                self.__control_values[port.name] = project_pb2.ControlValue(
                    value=port.float_value.default, generation=1)

        for control_value in self.__node.control_values:
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.append(
                control_value.value_changed.add(
                    functools.partial(self.__control_value_changed, control_value.name)))

        self.__control_values_listener = self.__node.control_values_changed.add(
            self.__control_values_changed)

        self.__initialized = True

    def cleanup(self) -> None:
        for listener in self.__control_value_listeners:
            listener.remove()
        self.__control_value_listeners.clear()

        if self.__control_values_listener is not None:
            self.__control_values_listener.remove()
            self.__control_values_listener = None

    def __control_values_changed(
            self, change: model_base.PropertyListChange[PipelineGraphControlValue]) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            control_value = change.new_value

            self.control_value_changed.call(
                control_value.name,
                model_base.PropertyValueChange(
                    self.__node, control_value.name,
                    self.__control_values[control_value.name], control_value.value))
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.insert(
                change.index,
                control_value.value_changed.add(
                    functools.partial(self.__control_value_changed, control_value.name)))

        elif isinstance(change, model_base.PropertyListDelete):
            control_value = change.old_value

            for port in self.__node.description.ports:
                if port.name == control_value.name:
                    default_value = project_pb2.ControlValue(
                        value=port.float_value.default, generation=1)
                    self.control_value_changed.call(
                        control_value.name,
                        model_base.PropertyValueChange(
                            self.__node, control_value.name,
                            self.__control_values[control_value.name], default_value))
                    self.__control_values[control_value.name] = default_value
                    break

            listener = self.__control_value_listeners.pop(change.index)
            listener.remove()

        else:
            raise TypeError(type(change))

    def __control_value_changed(
            self,
            control_value_name: str,
            change: model_base.PropertyValueChange[project_pb2.ControlValue]
    ) -> None:
        self.control_value_changed.call(
            control_value_name,
            model_base.PropertyValueChange(
                self.__node, control_value_name,
                self.__control_values[control_value_name], change.new_value))
        self.__control_values[control_value_name] = change.new_value


class BasePipelineGraphNode(ProjectChild):
    class BasePipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.base_pipeline_graph_node  # type: ignore

        name = model_base.Property(str)
        graph_pos = model_base.WrappedProtoProperty(pos2f.Pos2F)
        graph_size = model_base.WrappedProtoProperty(sizef.SizeF)
        graph_color = model_base.WrappedProtoProperty(
            color.Color, default=color.Color(0.8, 0.8, 0.8, 1.0))
        control_values = model_base.ObjectListProperty(PipelineGraphControlValue)
        plugin_state = model_base.ProtoProperty(audioproc.PluginState, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.graph_pos_changed = core.Callback[model_base.PropertyChange[pos2f.Pos2F]]()
        self.graph_size_changed = core.Callback[model_base.PropertyChange[sizef.SizeF]]()
        self.graph_color_changed = core.Callback[model_base.PropertyChange[color.Color]]()
        self.control_values_changed = \
            core.Callback[model_base.PropertyListChange[PipelineGraphControlValue]]()
        self.plugin_state_changed = \
            core.Callback[model_base.PropertyChange[audioproc.PluginState]]()

        self.control_value_map = ControlValueMap(self)

    @property
    def control_values(self) -> Sequence[PipelineGraphControlValue]:
        return self.get_property_value('control_values')

    @property
    def removable(self) -> bool:
        return True

    @property
    def description(self) -> node_db.NodeDescription:
        raise NotImplementedError

    def upstream_nodes(self) -> List['BasePipelineGraphNode']:
        node_ids = set()  # type: Set[int]
        self.__upstream_nodes(node_ids)
        return [self._pool[node_id] for node_id in sorted(node_ids)]

    def __upstream_nodes(self, seen: Set[int]) -> None:
        for connection in self.project.get_property_value('pipeline_graph_connections'):
            if connection.dest_node is self and connection.source_node.id not in seen:
                seen.add(connection.source_node.id)
                connection.source_node.__upstream_nodes(seen)


class PipelineGraphConnection(ProjectChild):
    class PipelineGraphConnectionSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_connection'
        proto_ext = project_pb2.pipeline_graph_connection  # type: ignore

        source_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        source_port = model_base.Property(str)
        dest_node = model_base.ObjectReferenceProperty(BasePipelineGraphNode)
        dest_port = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.source_node_changed = core.Callback[model_base.PropertyChange[BasePipelineGraphNode]]()
        self.source_port_changed = core.Callback[model_base.PropertyChange[str]]()
        self.dest_node_changed = core.Callback[model_base.PropertyChange[BasePipelineGraphNode]]()
        self.dest_port_changed = core.Callback[model_base.PropertyChange[str]]()


class PipelineGraphNode(BasePipelineGraphNode):
    class PipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_type = 'pipeline_graph_node'
        proto_ext = project_pb2.pipeline_graph_node  # type: ignore

        node_uri = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.node_uri_changed = core.Callback[model_base.PropertyChange[str]]()

    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @property
    def description(self) -> node_db.NodeDescription:
        return self.project.get_node_description(self.node_uri)


class AudioOutPipelineGraphNode(BasePipelineGraphNode):
    class AudioOutPipelineGraphNodeSpec(model_base.ObjectSpec):
        proto_type = 'audio_out_pipeline_graph_node'

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.RealmSinkDescription


class Track(BasePipelineGraphNode):  # pylint: disable=abstract-method
    class TrackSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.track  # type: ignore

        visible = model_base.Property(bool, default=True)
        list_position = model_base.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.visible_changed = core.Callback[model_base.PropertyChange[bool]]()
        self.list_position_changed = core.Callback[model_base.PropertyChange[int]]()
        self.duration_changed = core.Callback[None]()

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1, 1)


class Measure(ProjectChild):
    class MeasureSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.measure  # type: ignore

        time_signature = model_base.WrappedProtoProperty(
            time_signature_lib.TimeSignature,
            default=time_signature_lib.TimeSignature(4, 4))

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_signature_changed = \
            core.Callback[model_base.PropertyChange[time_signature_lib.TimeSignature]]()

    @property
    def track(self) -> Track:
        return cast(Track, self.parent)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        time_signature = self.get_property_value('time_signature')
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)


class MeasureReference(ProjectChild):
    class MeasureReferenceSpec(model_base.ObjectSpec):
        proto_type = 'measure_reference'
        proto_ext = project_pb2.measure_reference  # type: ignore

        measure = model_base.ObjectReferenceProperty(Measure)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.measure_changed = core.Callback[model_base.PropertyChange[Measure]]()

    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')

    @property
    def track(self) -> Track:
        return cast(Track, self.parent)

    @property
    def prev_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().prev_sibling)

    @property
    def next_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().next_sibling)


class MeasuredTrack(Track):  # pylint: disable=abstract-method
    class MeasuredSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.measured_track  # type: ignore

        measure_list = model_base.ObjectListProperty(MeasureReference)
        measure_heap = model_base.ObjectListProperty(Measure)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.measure_list_changed = core.Callback[model_base.PropertyListChange[MeasureReference]]()
        self.measure_heap_changed = core.Callback[model_base.PropertyListChange[Measure]]()

    def setup(self) -> None:
        super().setup()

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.measure_list_changed.add(self.__measure_list_changed)

    def __measure_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__add_measure(change.new_value)
        elif isinstance(change, model_base.PropertyListDelete):
            self.__remove_measure(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_measure(self, mref: MeasureReference) -> None:
        self.__listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda *_: self.__measure_changed(mref))
        self.duration_changed.call()

    def __remove_measure(self, mref: MeasureReference) -> None:
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.duration_changed.call()

    def __measure_changed(self, mref: MeasureReference) -> None:
        self.duration_changed.call()

    @property
    def measure_list(self) -> Sequence[MeasureReference]:
        return self.get_property_value('measure_list')

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = audioproc.MusicalDuration()
        for mref in self.measure_list:
            duration += mref.measure.duration
        return duration


class Metadata(ProjectChild):
    class MetadataSpec(model_base.ObjectSpec):
        proto_type = 'metadata'
        proto_ext = project_pb2.metadata  # type: ignore

        author = model_base.Property(str, allow_none=True)
        license = model_base.Property(str, allow_none=True)
        copyright = model_base.Property(str, allow_none=True)
        created = model_base.Property(int, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.author_changed = core.Callback[model_base.PropertyChange[str]]()
        self.license_changed = core.Callback[model_base.PropertyChange[str]]()
        self.copyright_changed = core.Callback[model_base.PropertyChange[str]]()
        self.created_changed = core.Callback[model_base.PropertyChange[int]]()


class Project(ObjectBase):
    class ProjectSpec(model_base.ObjectSpec):
        proto_type = 'project'
        proto_ext = project_pb2.project  # type: ignore

        metadata = model_base.ObjectProperty(Metadata)
        pipeline_graph_nodes = model_base.ObjectListProperty(BasePipelineGraphNode)
        pipeline_graph_connections = model_base.ObjectListProperty(PipelineGraphConnection)
        samples = model_base.ObjectListProperty(Sample)
        bpm = model_base.Property(int, default=120)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.metadata_changed = core.Callback[model_base.PropertyChange[Metadata]]()
        self.pipeline_graph_nodes_changed = \
            core.Callback[model_base.PropertyListChange[BasePipelineGraphNode]]()
        self.pipeline_graph_connections_changed = \
            core.Callback[model_base.PropertyListChange[PipelineGraphConnection]]()
        self.samples_changed = core.Callback[model_base.PropertyListChange[Sample]]()
        self.bpm_changed = core.Callback[model_base.PropertyChange[int]]()

        self.duration_changed = \
            core.Callback[model_base.PropertyChange[audioproc.MusicalDuration]]()
        self.pipeline_mutation = core.Callback[audioproc.Mutation]()

    @property
    def bpm(self) -> int:
        return self.get_property_value('bpm')

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(2 * 120, 4)  # 2min * 120bpm

    @property
    def attached_to_project(self) -> bool:
        return True

    def get_bpm(self, measure_idx: int, tick: int) -> int:  # pylint: disable=unused-argument
        return self.bpm

    @property
    def audio_out_node(self) -> AudioOutPipelineGraphNode:
        for node in self.get_property_value('pipeline_graph_nodes'):
            if isinstance(node, AudioOutPipelineGraphNode):
                return node

        raise ValueError("No audio out node found.")

    def get_node_description(self, uri: str) -> node_db.NodeDescription:
        raise NotImplementedError
