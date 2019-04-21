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
from typing import cast, Any, Optional, Iterator, Callable

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model
from . import pmodel
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
            'graph_pos': model.Pos2F.from_proto(pb.graph_pos),
            'graph_size': model.SizeF.from_proto(pb.graph_size),
            'graph_color': model.Color.from_proto(pb.graph_color),
        }

        # Defered import to work around cyclic import.
        from noisicaa.builtin_nodes import server_registry
        try:
            node_cls = server_registry.node_cls_map[pb.uri]
        except KeyError:
            node_cls = Node
            kwargs['node_uri'] = pb.uri

        node = self.pool.create(node_cls, id=None, **kwargs)
        self.pool.project.add_node(node)


class DeleteNode(commands.Command):
    proto_type = 'delete_node'

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteNode, self.pb)

        node = down_cast(pmodel.BaseNode, self.pool[pb.node_id])
        assert node.is_child_of(self.pool.project)

        self.pool.project.remove_node(node)


class CreateNodeConnection(commands.Command):
    proto_type = 'create_node_connection'

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateNodeConnection, self.pb)

        source_node = down_cast(pmodel.BaseNode, self.pool[pb.source_node_id])
        assert source_node.is_child_of(self.pool.project)
        dest_node = down_cast(pmodel.BaseNode, self.pool[pb.dest_node_id])
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

        connection = cast(pmodel.NodeConnection, self.pool[pb.connection_id])
        assert connection.is_child_of(self.pool.project)

        self.pool.project.remove_node_connection(connection)


class UpdateNode(commands.Command):
    proto_type = 'update_node'

    def validate(self) -> None:
        pb = down_cast(commands_pb2.UpdateNode, self.pb)

        if pb.node_id not in self.pool:
            raise ValueError("Unknown node %016x" % pb.node_id)

        node = down_cast(pmodel.BaseNode, self.pool[pb.node_id])

        if pb.HasField('set_port_properties'):
            if not any(
                    port_desc.name == pb.set_port_properties.name
                    for port_desc in node.description.ports):
                raise ValueError("Invalid port name '%s'" % pb.set_port_properties.name)

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateNode, self.pb)
        node = down_cast(pmodel.BaseNode, self.pool[pb.node_id])

        if pb.HasField('set_graph_pos'):
            node.graph_pos = model.Pos2F.from_proto(pb.set_graph_pos)

        if pb.HasField('set_graph_size'):
            node.graph_size = model.SizeF.from_proto(pb.set_graph_size)

        if pb.HasField('set_graph_color'):
            node.graph_color = model.Color.from_proto(pb.set_graph_color)

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
        port = down_cast(pmodel.Port, self.pool[pb.port_id])

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

# class NodeToPreset(commands.Command):
#     proto_type = 'node_to_preset'

#     def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> bytes:
#         pb = down_cast(commands_pb2.NodeToPreset, pb)
#         node = down_cast(pmodel.Node, pool[self.proto.command.target])

#         return node.to_preset()


# class NodeFromPreset(commands.Command):
#     proto_type = 'node_from_preset'

#     def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
#         pb = down_cast(commands_pb2.NodeFromPreset, pb)
#         node = down_cast(pmodel.Node, pool[self.proto.command.target])

#         node.from_preset(pb.preset)


class PresetLoadError(Exception):
    pass

class NotAPresetError(PresetLoadError):
    pass


class BaseNode(pmodel.BaseNode):  # pylint: disable=abstract-method
    def create(
            self, *,
            name: Optional[str] = None,
            graph_pos: model.Pos2F = model.Pos2F(0, 0),
            graph_size: model.SizeF = model.SizeF(140, 100),
            graph_color: model.Color = model.Color(0.8, 0.8, 0.8),
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.name = name
        self.graph_pos = graph_pos
        self.graph_size = graph_size
        self.graph_color = graph_color

    def setup(self) -> None:
        super().setup()
        self.description_changed.add(self.__description_changed)

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
                self.control_values[idx] = model.ControlValue(
                    name=name, value=value, generation=generation)
                break
        else:
            self.control_values.append(model.ControlValue(
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
                self.port_properties[idx] = model.NodePortProperties.from_proto(new_props)
                break
        else:
            new_props = port_properties
            self.port_properties.append(
                model.NodePortProperties.from_proto(port_properties))

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.Mutation(
                    set_node_port_properties=audioproc.SetNodePortProperties(
                        node_id=self.pipeline_node_id,
                        port_properties=new_props)))

    def __description_changed(self, change: model.PropertyChange) -> None:
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


class Port(pmodel.Port):  # pylint: disable=abstract-method
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

    def remove_connections(self) -> None:
        node = down_cast(BaseNode, self.parent)

        for conn in node.connections:
            if (conn.source_node is node and conn.source_port == self.name
                    or conn.dest_node is node and conn.dest_port == self.name):
                self.project.remove_node_connection(conn)


class Node(pmodel.Node, BaseNode):
    def create(self, *, node_uri: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.node_uri = node_uri

    def to_preset(self) -> bytes:
        raise NotImplementedError
        # doc = ElementTree.Element('preset', version='1')  # type: ignore
        # doc.text = '\n'
        # doc.tail = '\n'

        # display_name_elem = ElementTree.SubElement(doc, 'display-name')
        # display_name_elem.text = "User preset"
        # display_name_elem.tail = '\n'

        # node_uri_elem = ElementTree.SubElement(doc, 'node', uri=self.node_uri)
        # node_uri_elem.tail = '\n'

        # tree = ElementTree.ElementTree(doc)
        # buf = io.BytesIO()
        # tree.write(buf, encoding='utf-8', xml_declaration=True)
        # return buf.getvalue()

    def from_preset(self, xml: bytes) -> None:
        raise NotImplementedError
        # preset = node_db.Preset.parse(io.BytesIO(xml), self.project.get_node_description)

        # if preset.node_uri != self.node_uri:
        #     raise node_db.PresetLoadError(
        #         "Mismatching node_uri (Expected %s, got %s)."
        #         % (self.node_uri, preset.node_uri))


class SystemOutNode(pmodel.SystemOutNode, BaseNode):
    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []


class NodeConnection(pmodel.NodeConnection):
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
