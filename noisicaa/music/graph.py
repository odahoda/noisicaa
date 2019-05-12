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
from typing import cast, Any, Optional, List, Dict, Set, Iterator, Callable, Sequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import value_types
from . import model_base
from . import _model
from . import node_connector

logger = logging.getLogger(__name__)


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


class BaseNode(_model.BaseNode, model_base.ProjectChild):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

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

    def set_port_properties(self, port_properties: value_types.NodePortProperties) -> None:
        assert any(port_desc.name == port_properties.name for port_desc in self.description.ports)

        new_props = None  # type: audioproc.NodePortProperties

        for idx, props in enumerate(self.port_properties):
            if props.name == port_properties.name:
                new_props = props.to_proto()
                new_props.MergeFrom(port_properties.to_proto())
                self.port_properties[idx] = value_types.NodePortProperties.from_proto(new_props)
                break
        else:
            new_props = port_properties.to_proto()
            self.port_properties.append(port_properties)

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


class Port(_model.Port, model_base.ProjectChild):
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

    def _validate_name(self, value: str) -> None:
        if value != self.get_property_value('name', allow_unset=True):
            self.remove_connections()

    def _validate_type(self, value: int) -> None:
        if value != self.get_property_value('type', allow_unset=True):
            self.remove_connections()

    def _validate_direction(self, value: int) -> None:
        if value != self.get_property_value('direction', allow_unset=True):
            self.remove_connections()

    def remove_connections(self) -> None:
        node = down_cast(BaseNode, self.parent)
        if node is not None:
            for conn in node.connections:
                if (conn.source_node is node and conn.source_port == self.name
                        or conn.dest_node is node and conn.dest_port == self.name):
                    self.project.remove_node_connection(conn)


class Node(_model.Node, BaseNode):
    def create(self, *, node_uri: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.node_uri = node_uri

    @property
    def description(self) -> node_db.NodeDescription:
        return self.project.get_node_description(self.node_uri)


class SystemOutNode(_model.SystemOutNode, BaseNode):
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


class NodeConnection(_model.NodeConnection, model_base.ProjectChild):
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
