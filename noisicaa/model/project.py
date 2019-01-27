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
from typing import cast, Any, Dict, Set, Sequence, List

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from . import time_signature as time_signature_lib
from . import pos2f
from . import sizef
from . import color
from . import control_value
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
        proto_ext = project_pb2.sample

        path = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.path_changed = core.Callback[model_base.PropertyChange[str]]()


class ControlValueMap(object):
    def __init__(self, node: 'BaseNode') -> None:
        self.__node = node

        self.__initialized = False
        self.__control_values = {}  # type: Dict[str, control_value.ControlValue]
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
                self.__control_values[port.name] = control_value.ControlValue(
                    name=port.name, value=port.float_value.default, generation=1)

        for cv in self.__node.control_values:
            self.__control_values[cv.name] = cv

        self.__control_values_listener = self.__node.control_values_changed.add(
            self.__control_values_changed)

        self.__initialized = True

    def cleanup(self) -> None:
        if self.__control_values_listener is not None:
            self.__control_values_listener.remove()
            self.__control_values_listener = None

    def __control_values_changed(
            self, change: model_base.PropertyListChange[control_value.ControlValue]) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            new_value = change.new_value
            old_value = self.__control_values[new_value.name]

            self.control_value_changed.call(
                new_value.name,
                model_base.PropertyValueChange(
                    self.__node, new_value.name, old_value, new_value))
            self.__control_values[new_value.name] = new_value

        elif isinstance(change, model_base.PropertyListDelete):
            pass

        elif isinstance(change, model_base.PropertyListSet):
            new_value = change.new_value
            old_value = self.__control_values[new_value.name]

            self.control_value_changed.call(
                new_value.name,
                model_base.PropertyValueChange(
                    self.__node, new_value.name, old_value, new_value))
            self.__control_values[new_value.name] = new_value

        else:
            raise TypeError(type(change))


class BaseNode(ProjectChild):
    class BaseNodeSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.base_node

        name = model_base.Property(str)
        graph_pos = model_base.WrappedProtoProperty(pos2f.Pos2F)
        graph_size = model_base.WrappedProtoProperty(sizef.SizeF)
        graph_color = model_base.WrappedProtoProperty(
            color.Color, default=color.Color(0.8, 0.8, 0.8, 1.0))
        control_values = model_base.WrappedProtoListProperty(control_value.ControlValue)
        plugin_state = model_base.ProtoProperty(audioproc.PluginState, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.graph_pos_changed = core.Callback[model_base.PropertyChange[pos2f.Pos2F]]()
        self.graph_size_changed = core.Callback[model_base.PropertyChange[sizef.SizeF]]()
        self.graph_color_changed = core.Callback[model_base.PropertyChange[color.Color]]()
        self.control_values_changed = \
            core.Callback[model_base.PropertyListChange[control_value.ControlValue]]()
        self.plugin_state_changed = \
            core.Callback[model_base.PropertyChange[audioproc.PluginState]]()

        self.control_value_map = ControlValueMap(self)

    @property
    def control_values(self) -> Sequence[control_value.ControlValue]:
        return self.get_property_value('control_values')

    @property
    def pipeline_node_id(self) -> str:
        return '%016x' % self.id

    @property
    def removable(self) -> bool:
        return True

    @property
    def description(self) -> node_db.NodeDescription:
        raise NotImplementedError

    def upstream_nodes(self) -> List['BaseNode']:
        node_ids = set()  # type: Set[int]
        self.__upstream_nodes(node_ids)
        return [self._pool[node_id] for node_id in sorted(node_ids)]

    def __upstream_nodes(self, seen: Set[int]) -> None:
        for connection in self.project.get_property_value('node_connections'):
            if connection.dest_node is self and connection.source_node.id not in seen:
                seen.add(connection.source_node.id)
                connection.source_node.__upstream_nodes(seen)


class NodeConnection(ProjectChild):
    class NodeConnectionSpec(model_base.ObjectSpec):
        proto_type = 'node_connection'
        proto_ext = project_pb2.node_connection

        source_node = model_base.ObjectReferenceProperty(BaseNode)
        source_port = model_base.Property(str)
        dest_node = model_base.ObjectReferenceProperty(BaseNode)
        dest_port = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.source_node_changed = core.Callback[model_base.PropertyChange[BaseNode]]()
        self.source_port_changed = core.Callback[model_base.PropertyChange[str]]()
        self.dest_node_changed = core.Callback[model_base.PropertyChange[BaseNode]]()
        self.dest_port_changed = core.Callback[model_base.PropertyChange[str]]()


class Node(BaseNode):
    class NodeSpec(model_base.ObjectSpec):
        proto_type = 'node'
        proto_ext = project_pb2.node

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


class SystemOutNode(BaseNode):
    class SystemOutNodeSpec(model_base.ObjectSpec):
        proto_type = 'system_out_node'

    @property
    def pipeline_node_id(self) -> str:
        return 'sink'

    @property
    def removable(self) -> bool:
        return False

    @property
    def description(self) -> node_db.NodeDescription:
        return node_db.Builtins.RealmSinkDescription


class Track(BaseNode):  # pylint: disable=abstract-method
    class TrackSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.track

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
        proto_ext = project_pb2.measure

        time_signature = model_base.WrappedProtoProperty(
            time_signature_lib.TimeSignature,
            default=time_signature_lib.TimeSignature(4, 4))

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_signature_changed = \
            core.Callback[model_base.PropertyChange[time_signature_lib.TimeSignature]]()

    @property
    def track(self) -> 'MeasuredTrack':
        return cast(MeasuredTrack, self.parent)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        time_signature = self.get_property_value('time_signature')
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)


class MeasureReference(ProjectChild):
    class MeasureReferenceSpec(model_base.ObjectSpec):
        proto_type = 'measure_reference'
        proto_ext = project_pb2.measure_reference

        measure = model_base.ObjectReferenceProperty(Measure)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.measure_changed = core.Callback[model_base.PropertyChange[Measure]]()

    @property
    def measure(self) -> Measure:
        return self.get_property_value('measure')

    @property
    def track(self) -> 'MeasuredTrack':
        return cast(MeasuredTrack, self.parent)

    @property
    def prev_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().prev_sibling)

    @property
    def next_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().next_sibling)


class MeasuredTrack(Track):  # pylint: disable=abstract-method
    class MeasuredSpec(model_base.ObjectSpec):
        proto_ext = project_pb2.measured_track

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
        proto_ext = project_pb2.metadata

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
        proto_ext = project_pb2.project

        metadata = model_base.ObjectProperty(Metadata)
        nodes = model_base.ObjectListProperty(BaseNode)
        node_connections = model_base.ObjectListProperty(NodeConnection)
        samples = model_base.ObjectListProperty(Sample)
        bpm = model_base.Property(int, default=120)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.metadata_changed = core.Callback[model_base.PropertyChange[Metadata]]()
        self.nodes_changed = core.Callback[model_base.PropertyListChange[BaseNode]]()
        self.node_connections_changed = \
            core.Callback[model_base.PropertyListChange[NodeConnection]]()
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
    def system_out_node(self) -> SystemOutNode:
        for node in self.get_property_value('nodes'):
            if isinstance(node, SystemOutNode):
                return node

        raise ValueError("No system out node found.")

    def get_node_description(self, uri: str) -> node_db.NodeDescription:
        raise NotImplementedError
