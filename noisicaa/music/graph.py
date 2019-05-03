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
from typing import (
    cast, Any, Optional, List, Dict, Set, Iterator, Callable, Sequence, MutableSequence)

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model_base
from noisicaa import value_types
from . import model
from . import model_pb2
from . import node_connector
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class CreateNode(commands.Command):
    proto_type = 'create_node'

    def validate(self) -> None:
        pb = down_cast(commands_pb2.CreateNode, self.pb)

        # Ensure the requested URI is valid.
        self.pool.project.get_node_description(pb.uri)

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateNode, self.pb)

        node_desc = self.pool.project.get_node_description(pb.uri)

        kwargs = {
            'name': pb.name or node_desc.display_name,
            'graph_pos': value_types.Pos2F.from_proto(pb.graph_pos),
            'graph_size': value_types.SizeF.from_proto(pb.graph_size),
            'graph_color': value_types.Color.from_proto(pb.graph_color),
        }

        # Defered import to work around cyclic import.
        from noisicaa.builtin_nodes import model_registry
        try:
            node_cls = model_registry.node_cls_map[pb.uri]
        except KeyError:
            node_cls = Node
            kwargs['node_uri'] = pb.uri

        node = self.pool.create(node_cls, id=None, **kwargs)
        self.pool.project.add_node(node)


class DeleteNode(commands.Command):
    proto_type = 'delete_node'

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteNode, self.pb)

        node = down_cast(BaseNode, self.pool[pb.node_id])
        assert node.is_child_of(self.pool.project)

        self.pool.project.remove_node(node)


class CreateNodeConnection(commands.Command):
    proto_type = 'create_node_connection'

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateNodeConnection, self.pb)

        source_node = down_cast(BaseNode, self.pool[pb.source_node_id])
        assert source_node.is_child_of(self.pool.project)
        dest_node = down_cast(BaseNode, self.pool[pb.dest_node_id])
        assert dest_node.is_child_of(self.pool.project)

        connection = self.pool.create(
            NodeConnection,
            source_node=source_node, source_port=pb.source_port_name,
            dest_node=dest_node, dest_port=pb.dest_port_name)
        self.pool.project.add_node_connection(connection)


class DeleteNodeConnection(commands.Command):
    proto_type = 'delete_node_connection'

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteNodeConnection, self.pb)

        connection = cast(NodeConnection, self.pool[pb.connection_id])
        assert connection.is_child_of(self.pool.project)

        self.pool.project.remove_node_connection(connection)


class UpdateNode(commands.Command):
    proto_type = 'update_node'

    def validate(self) -> None:
        pb = down_cast(commands_pb2.UpdateNode, self.pb)

        if pb.node_id not in self.pool:
            raise ValueError("Unknown node %016x" % pb.node_id)

        node = down_cast(BaseNode, self.pool[pb.node_id])

        if pb.HasField('set_port_properties'):
            if not any(
                    port_desc.name == pb.set_port_properties.name
                    for port_desc in node.description.ports):
                raise ValueError("Invalid port name '%s'" % pb.set_port_properties.name)

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateNode, self.pb)
        node = down_cast(BaseNode, self.pool[pb.node_id])

        if pb.HasField('set_graph_pos'):
            node.graph_pos = value_types.Pos2F.from_proto(pb.set_graph_pos)

        if pb.HasField('set_graph_size'):
            node.graph_size = value_types.SizeF.from_proto(pb.set_graph_size)

        if pb.HasField('set_graph_color'):
            node.graph_color = value_types.Color.from_proto(pb.set_graph_color)

        if pb.HasField('set_name'):
            node.name = pb.set_name

        if pb.HasField('set_plugin_state'):
            node.set_plugin_state(pb.set_plugin_state)

        if pb.HasField('set_control_value'):
            node.set_control_value(
                pb.set_control_value.name,
                pb.set_control_value.value,
                pb.set_control_value.generation)

        if pb.HasField('set_port_properties'):
            node.set_port_properties(pb.set_port_properties)


class UpdatePort(commands.Command):
    proto_type = 'update_port'

    def validate(self) -> None:
        pb = down_cast(commands_pb2.UpdatePort, self.pb)

        if pb.port_id not in self.pool:
            raise ValueError("Unknown port %016x" % pb.port_id)

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdatePort, self.pb)
        port = down_cast(Port, self.pool[pb.port_id])

        remove_connections = (
            pb.HasField('set_name')
            or pb.HasField('set_type')
            or pb.HasField('set_direction'))
        if remove_connections:
            port.remove_connections()

        if pb.HasField('set_name'):
            port.name = pb.set_name

        if pb.HasField('set_display_name'):
            port.display_name = pb.set_display_name

        if pb.HasField('set_type'):
            port.type = pb.set_type

        if pb.HasField('set_direction'):
            port.direction = pb.set_direction


class ControlValueMap(object):
    def __init__(self, node: 'BaseNode') -> None:
        self.__node = node

        self.__initialized = False
        self.__control_values = {}  # type: Dict[str, value_types.ControlValue]
        self.__control_values_listener = None # type: core.Listener

        self.control_value_changed = core.CallbackMap[str, model_base.PropertyValueChange]()

    def __get(self, name: str) -> value_types.ControlValue:
        try:
            return self.__control_values[name]
        except KeyError:
            for port in self.__node.description.ports:
                if (port.name == name
                        and port.direction == node_db.PortDescription.INPUT
                        and port.type in (node_db.PortDescription.KRATE_CONTROL,
                                          node_db.PortDescription.ARATE_CONTROL)):
                    return value_types.ControlValue(
                        name=port.name, value=port.float_value.default, generation=1)

            raise

    def value(self, name: str) -> float:
        return self.__get(name).value

    def generation(self, name: str) -> int:
        return self.__get(name).generation

    def init(self) -> None:
        if self.__initialized:
            return

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
            self, change: model_base.PropertyListChange[value_types.ControlValue]) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            new_value = change.new_value
            old_value = self.__get(new_value.name)

            self.control_value_changed.call(
                new_value.name,
                model_base.PropertyValueChange(
                    self.__node, new_value.name, old_value, new_value))
            self.__control_values[new_value.name] = new_value

        elif isinstance(change, model_base.PropertyListDelete):
            pass

        elif isinstance(change, model_base.PropertyListSet):
            new_value = change.new_value
            old_value = self.__get(new_value.name)

            self.control_value_changed.call(
                new_value.name,
                model_base.PropertyValueChange(
                    self.__node, new_value.name, old_value, new_value))
            self.__control_values[new_value.name] = new_value

        else:
            raise TypeError(type(change))


class BaseNode(model.ProjectChild):
    class BaseNodeSpec(model_base.ObjectSpec):
        proto_ext = model_pb2.base_node

        name = model_base.Property(str)
        graph_pos = model_base.WrappedProtoProperty(value_types.Pos2F)
        graph_size = model_base.WrappedProtoProperty(value_types.SizeF)
        graph_color = model_base.WrappedProtoProperty(
            value_types.Color, default=value_types.Color(0.8, 0.8, 0.8, 1.0))
        control_values = model_base.WrappedProtoListProperty(value_types.ControlValue)
        plugin_state = model_base.ProtoProperty(audioproc.PluginState, allow_none=True)
        port_properties = model_base.WrappedProtoListProperty(
            value_types.NodePortProperties)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.graph_pos_changed = core.Callback[model_base.PropertyChange[value_types.Pos2F]]()
        self.graph_size_changed = core.Callback[model_base.PropertyChange[value_types.SizeF]]()
        self.graph_color_changed = core.Callback[model_base.PropertyChange[value_types.Color]]()
        self.control_values_changed = \
            core.Callback[model_base.PropertyListChange[value_types.ControlValue]]()
        self.plugin_state_changed = \
            core.Callback[model_base.PropertyChange[audioproc.PluginState]]()
        self.port_properties_changed = \
            core.Callback[model_base.PropertyListChange[value_types.NodePortProperties]]()

        self.description_changed = core.Callback[model_base.PropertyChange]()

        self.control_value_map = ControlValueMap(self)

    def create(
            self, *,
            name: Optional[str] = None,
            graph_pos: value_types.Pos2F = value_types.Pos2F(0, 0),
            graph_size: value_types.SizeF = value_types.SizeF(140, 100),
            graph_color: value_types.Color = value_types.Color(0.8, 0.8, 0.8),
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.name = name
        self.graph_pos = graph_pos
        self.graph_size = graph_size
        self.graph_color = graph_color

    def setup(self) -> None:
        super().setup()
        self.description_changed.add(self.__description_changed)

    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def graph_pos(self) -> value_types.Pos2F:
        return self.get_property_value('graph_pos')

    @graph_pos.setter
    def graph_pos(self, value: value_types.Pos2F) -> None:
        self.set_property_value('graph_pos', value)

    @property
    def graph_size(self) -> value_types.SizeF:
        return self.get_property_value('graph_size')

    @graph_size.setter
    def graph_size(self, value: value_types.SizeF) -> None:
        self.set_property_value('graph_size', value)

    @property
    def graph_color(self) -> value_types.Color:
        return self.get_property_value('graph_color')

    @graph_color.setter
    def graph_color(self, value: value_types.Color) -> None:
        self.set_property_value('graph_color', value)

    @property
    def control_values(self) -> MutableSequence[value_types.ControlValue]:
        return self.get_property_value('control_values')

    @property
    def plugin_state(self) -> audioproc.PluginState:
        return self.get_property_value('plugin_state')

    @plugin_state.setter
    def plugin_state(self, value: audioproc.PluginState) -> None:
        self.set_property_value('plugin_state', value)

    @property
    def port_properties(self) -> MutableSequence[value_types.NodePortProperties]:
        return self.get_property_value('port_properties')

    def get_port_properties(self, port_name: str) -> value_types.NodePortProperties:
        for np in self.port_properties:
            if np.name == port_name:
                return np

        return value_types.NodePortProperties(port_name)

    @property
    def pipeline_node_id(self) -> str:
        return '%016x' % self.id

    @property
    def removable(self) -> bool:
        return True

    @property
    def description(self) -> node_db.NodeDescription:
        raise NotImplementedError

    @property
    def connections(self) -> Sequence['NodeConnection']:
        result = []
        for conn in self.project.get_property_value('node_connections'):
            if conn.source_node is self or conn.dest_node is self:
                result.append(conn)

        return result

    def upstream_nodes(self) -> List['BaseNode']:
        node_ids = set()  # type: Set[int]
        self.__upstream_nodes(node_ids)
        return [cast(BaseNode, self._pool[node_id]) for node_id in sorted(node_ids)]

    def __upstream_nodes(self, seen: Set[int]) -> None:
        for connection in self.project.get_property_value('node_connections'):
            if connection.dest_node is self and connection.source_node.id not in seen:
                seen.add(connection.source_node.id)
                connection.source_node.__upstream_nodes(seen)

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.Mutation(
            add_node=audioproc.AddNode(
                description=self.description,
                id=self.pipeline_node_id,
                name=self.name,
                initial_state=self.plugin_state))

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.Mutation(
            remove_node=audioproc.RemoveNode(id=self.pipeline_node_id))

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        for props in self.port_properties:
            yield audioproc.Mutation(
                set_node_port_properties=audioproc.SetNodePortProperties(
                    node_id=self.pipeline_node_id,
                    port_properties=props.to_proto()))

        for port in self.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and (port.type == node_db.PortDescription.KRATE_CONTROL,
                         port.type == node_db.PortDescription.ARATE_CONTROL)):
                for cv in self.control_values:
                    if cv.name == port.name:
                        yield audioproc.Mutation(
                            set_control_value=audioproc.SetControlValue(
                                name='%s:%s' % (self.pipeline_node_id, cv.name),
                                value=cv.value,
                                generation=cv.generation))

    def set_control_value(self, name: str, value: float, generation: int) -> None:
        for idx, control_value in enumerate(self.control_values):
            if control_value.name == name:
                if generation < control_value.generation:
                    return
                self.control_values[idx] = value_types.ControlValue(
                    name=name, value=value, generation=generation)
                break
        else:
            self.control_values.append(value_types.ControlValue(
                name=name, value=value, generation=generation))

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.Mutation(
                    set_control_value=audioproc.SetControlValue(
                        name='%s:%s' % (self.pipeline_node_id, name),
                        value=value,
                        generation=generation)))

    def set_plugin_state(self, plugin_state: audioproc.PluginState) -> None:
        self.plugin_state = plugin_state

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.Mutation(
                    set_plugin_state=audioproc.SetPluginState(
                        node_id=self.pipeline_node_id,
                        state=plugin_state)))

    def set_port_properties(self, port_properties: audioproc.NodePortProperties) -> None:
        new_props = None  # type: audioproc.NodePortProperties

        for idx, props in enumerate(self.port_properties):
            if props.name == port_properties.name:
                new_props = props.to_proto()
                new_props.MergeFrom(port_properties)
                self.port_properties[idx] = value_types.NodePortProperties.from_proto(new_props)
                break
        else:
            new_props = port_properties
            self.port_properties.append(
                value_types.NodePortProperties.from_proto(port_properties))

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.Mutation(
                    set_node_port_properties=audioproc.SetNodePortProperties(
                        node_id=self.pipeline_node_id,
                        port_properties=new_props)))

    def __description_changed(self, change: model_base.PropertyChange) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(audioproc.Mutation(
                set_node_description=audioproc.SetNodeDescription(
                    node_id=self.pipeline_node_id,
                    description=self.description)))

    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> node_connector.NodeConnector:
        return None


class Port(model.ProjectChild):
    class PortSpec(model_base.ObjectSpec):
        proto_ext = model_pb2.port

        name = model_base.Property(str)
        display_name = model_base.Property(str, allow_none=True)
        type = model_base.Property(node_db.PortDescription.Type)
        direction = model_base.Property(node_db.PortDescription.Direction)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.display_name_changed = core.Callback[model_base.PropertyChange[str]]()
        self.type_changed = core.Callback[model_base.PropertyChange[int]]()
        self.direction_changed = core.Callback[model_base.PropertyChange[int]]()

    def create(
            self, *,
            name: Optional[str] = None,
            display_name: Optional[str] = None,
            type: Optional[int] = None,  # pylint: disable=redefined-builtin
            direction: Optional[int] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.name = name
        self.display_name = display_name
        self.type = cast(node_db.PortDescription.Type, type)
        self.direction = cast(node_db.PortDescription.Direction, direction)

    @property
    def name(self) -> str:
        return self.get_property_value('name')

    @name.setter
    def name(self, value: str) -> None:
        self.set_property_value('name', value)

    @property
    def display_name(self) -> str:
        return self.get_property_value('display_name')

    @display_name.setter
    def display_name(self, value: str) -> None:
        self.set_property_value('display_name', value)

    @property
    def type(self) -> node_db.PortDescription.Type:
        return self.get_property_value('type')

    @type.setter
    def type(self, value: node_db.PortDescription.Type) -> None:
        self.set_property_value('type', value)

    @property
    def direction(self) -> node_db.PortDescription.Direction:
        return self.get_property_value('direction')

    @direction.setter
    def direction(self, value: node_db.PortDescription.Direction) -> None:
        self.set_property_value('direction', value)

    def remove_connections(self) -> None:
        node = down_cast(BaseNode, self.parent)

        for conn in node.connections:
            if (conn.source_node is node and conn.source_port == self.name
                    or conn.dest_node is node and conn.dest_port == self.name):
                self.project.remove_node_connection(conn)


class Node(BaseNode):
    class NodeSpec(model_base.ObjectSpec):
        proto_type = 'node'
        proto_ext = model_pb2.node

        node_uri = model_base.Property(str)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.node_uri_changed = core.Callback[model_base.PropertyChange[str]]()

    def create(self, *, node_uri: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.node_uri = node_uri

    @property
    def node_uri(self) -> str:
        return self.get_property_value('node_uri')

    @node_uri.setter
    def node_uri(self, value: str) -> None:
        self.set_property_value('node_uri', value)

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

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []


class NodeConnection(model.ProjectChild):
    class NodeConnectionSpec(model_base.ObjectSpec):
        proto_type = 'node_connection'
        proto_ext = model_pb2.node_connection

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

    def create(
            self, *,
            source_node: Optional[BaseNode] = None,
            source_port: Optional[str] = None,
            dest_node: Optional[BaseNode] = None,
            dest_port: Optional[str] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.source_node = source_node
        self.source_port = source_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    @property
    def source_node(self) -> BaseNode:
        return self.get_property_value('source_node')

    @source_node.setter
    def source_node(self, value: BaseNode) -> None:
        self.set_property_value('source_node', value)

    @property
    def source_port(self) -> str:
        return self.get_property_value('source_port')

    @source_port.setter
    def source_port(self, value: str) -> None:
        self.set_property_value('source_port', value)

    @property
    def dest_node(self) -> BaseNode:
        return self.get_property_value('dest_node')

    @dest_node.setter
    def dest_node(self, value: BaseNode) -> None:
        self.set_property_value('dest_node', value)

    @property
    def dest_port(self) -> str:
        return self.get_property_value('dest_port')

    @dest_port.setter
    def dest_port(self, value: str) -> None:
        self.set_property_value('dest_port', value)

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.Mutation(
            connect_ports=audioproc.ConnectPorts(
                src_node_id=self.source_node.pipeline_node_id,
                src_port=self.source_port,
                dest_node_id=self.dest_node.pipeline_node_id,
                dest_port=self.dest_port))

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.Mutation(
            disconnect_ports=audioproc.DisconnectPorts(
                src_node_id=self.source_node.pipeline_node_id,
                src_port=self.source_port,
                dest_node_id=self.dest_node.pipeline_node_id,
                dest_port=self.dest_port))
