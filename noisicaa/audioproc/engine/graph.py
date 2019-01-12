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
from typing import Any, Dict, List, Optional, Set

import toposort

from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import host_system as host_system_lib
from noisicaa.audioproc.public import processor_message_pb2
from . import control_value
from . import processor as processor_lib
from . import processor_pb2
from . import plugin_host_pb2
from . import buffers
from . import spec as spec_lib
from . import realm as realm_lib

logger = logging.getLogger(__name__)


class GraphError(Exception):
    pass


class Port(object):
    def __init__(self, *, description: node_db.PortDescription) -> None:
        self.__description = description
        self.owner = None  # type: Node

    def __str__(self) -> str:
        return '<%s %s:%s>' % (
            type(self).__name__,
            self.owner.id if self.owner is not None else 'None',
            self.name)

    @property
    def description(self) -> node_db.PortDescription:
        return self.__description

    @property
    def name(self) -> str:
        return self.__description.name

    @property
    def buf_name(self) -> str:
        return '%s:%s' % (self.owner.id, self.__description.name)

    def get_buf_type(self) -> buffers.PyBufferType:
        raise NotImplementedError(type(self).__name__)

    def set_prop(self, **kwargs: Any) -> None:
        assert not kwargs


class InputPortMixin(Port):
    # pylint: disable=abstract-method

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.inputs = []  # type: List[Port]

    def connect(self, port: Port) -> None:
        self.check_port(port)
        self.inputs.append(port)

    def disconnect(self, port: Port) -> None:
        assert port in self.inputs, port
        self.inputs.remove(port)

    def check_port(self, port: Port) -> None:
        if not isinstance(port, OutputPortMixin):
            raise GraphError("Can only connect to output ports")


class OutputPortMixin(Port):
    # pylint: disable=abstract-method

    def __init__(self, *, bypass_port: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bypass = False
        self._bypass_port = bypass_port

    @property
    def bypass_port(self) -> Optional[str]:
        return self._bypass_port

    @property
    def bypass(self) -> bool:
        return self._bypass

    @bypass.setter
    def bypass(self, value: bool) -> None:
        assert self._bypass_port is not None
        self._bypass = bool(value)

    def set_prop(self, *, bypass: Optional[bool] = None, **kwargs: Any) -> None:
        super().set_prop(**kwargs)
        if bypass is not None:
            self.bypass = bypass


class AudioPortMixin(Port):
    def get_buf_type(self) -> buffers.PyBufferType:
        return buffers.PyFloatAudioBlockBuffer()


class ARateControlPortMixin(Port):
    def get_buf_type(self) -> buffers.PyBufferType:
        return buffers.PyFloatAudioBlockBuffer()


class KRateControlPortMixin(Port):
    def get_buf_type(self) -> buffers.PyBufferType:
        return buffers.PyFloatControlValueBuffer()


class EventPortMixin(Port):
    def get_buf_type(self) -> buffers.PyBufferType:
        return buffers.PyAtomDataBuffer()


class AudioInputPort(AudioPortMixin, InputPortMixin, Port):
    def check_port(self, port: Port) -> None:
        super().check_port(port)
        if not isinstance(port, AudioOutputPort):
            raise GraphError("Can only connect to AudioOutputPort")


class AudioOutputPort(AudioPortMixin, OutputPortMixin, Port):
    def __init__(self, *, drywet_port: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._drywet = 0.0
        self._drywet_port = drywet_port

    @property
    def drywet_port(self) -> str:
        return self._drywet_port

    @property
    def drywet(self) -> float:
        return self._drywet

    @drywet.setter
    def drywet(self, value: float) -> None:
        value = float(value)
        if value < -100.0 or value > 100.0:
            raise ValueError("Invalid dry/wet value.")
        self._drywet = float(value)

    def set_prop(self, *, drywet: Optional[float] = None, **kwargs: Any) -> None:
        super().set_prop(**kwargs)
        if drywet is not None:
            self.drywet = drywet


class ARateControlInputPort(ARateControlPortMixin, InputPortMixin, Port):
    def check_port(self, port: Port) -> None:
        super().check_port(port)
        if not isinstance(port, ARateControlOutputPort):
            raise GraphError("Can only connect to ARateControlOutputPort")


class ARateControlOutputPort(ARateControlPortMixin, OutputPortMixin, Port):
    pass


class KRateControlInputPort(KRateControlPortMixin, InputPortMixin, Port):
    def check_port(self, port: Port) -> None:
        super().check_port(port)
        if not isinstance(port, KRateControlOutputPort):
            raise GraphError("Can only connect to KRateControlOutputPort")


class KRateControlOutputPort(KRateControlPortMixin, OutputPortMixin, Port):
    pass


class EventInputPort(EventPortMixin, InputPortMixin, Port):
    def __init__(self, *, csound_instr: str = '1', **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.csound_instr = csound_instr

    def check_port(self, port: Port) -> None:
        super().check_port(port)
        if not isinstance(port, EventOutputPort):
            raise GraphError("Can only connect to EventOutputPort")


class EventOutputPort(EventPortMixin, OutputPortMixin, Port):
    pass


class Node(object):
    init_ports_from_description = True

    def __init__(
            self, *,
            host_system: host_system_lib.HostSystem, description: node_db.NodeDescription,
            id: str,  # pylint: disable=redefined-builtin
            name: Optional[str] = None, initial_state: Optional[audioproc.PluginState] = None
    ) -> None:
        assert isinstance(description, node_db.NodeDescription), description

        self._host_system = host_system
        self.description = description
        self.name = name or type(self).__name__
        self.id = id
        self.initial_state = initial_state

        self.__realm = None  # type: realm_lib.PyRealm
        self.broken = False
        self.ports = []  # type: List[Port]
        self.inputs = {}  # type: Dict[str, InputPortMixin]
        self.outputs = {}  # type: Dict[str, OutputPortMixin]

        self.__control_values = {}  # type: Dict[str, control_value.PyControlValue]

        if self.init_ports_from_description:
            self.init_ports()

    @classmethod
    def create(cls, *, description: node_db.NodeDescription, **kwargs: Any) -> 'Node':
        cls_map = {
            node_db.NodeDescription.PROCESSOR: ProcessorNode,
            node_db.NodeDescription.PLUGIN: PluginNode,
            node_db.NodeDescription.REALM_SINK: RealmSinkNode,
            node_db.NodeDescription.CHILD_REALM: ChildRealmNode,
        }

        try:
            node_cls = cls_map[description.type]
        except KeyError:
            raise ValueError("Unsupported node type %d" % description.type)

        return node_cls(description=description, **kwargs)

    @property
    def realm(self) -> realm_lib.PyRealm:
        assert self.__realm is not None
        return self.__realm

    def set_realm(self, realm: realm_lib.PyRealm) -> None:
        assert self.__realm is None
        self.__realm = realm

    def clear_realm(self) -> None:
        self.__realm = None

    def is_owned_by(self, realm: realm_lib.PyRealm) -> bool:
        return self.__realm is realm

    def init_ports(self) -> None:
        port_cls_map = {
            (node_db.PortDescription.AUDIO,
             node_db.PortDescription.INPUT): AudioInputPort,
            (node_db.PortDescription.AUDIO,
             node_db.PortDescription.OUTPUT): AudioOutputPort,
            (node_db.PortDescription.ARATE_CONTROL,
             node_db.PortDescription.INPUT): ARateControlInputPort,
            (node_db.PortDescription.ARATE_CONTROL,
             node_db.PortDescription.OUTPUT): ARateControlOutputPort,
            (node_db.PortDescription.KRATE_CONTROL,
             node_db.PortDescription.INPUT): KRateControlInputPort,
            (node_db.PortDescription.KRATE_CONTROL,
             node_db.PortDescription.OUTPUT): KRateControlOutputPort,
            (node_db.PortDescription.EVENTS,
             node_db.PortDescription.INPUT): EventInputPort,
            (node_db.PortDescription.EVENTS,
             node_db.PortDescription.OUTPUT): EventOutputPort,
        }

        for port_desc in self.description.ports:
            port_cls = port_cls_map[
                (port_desc.type, port_desc.direction)]
            kwargs = {}

            if port_desc.HasField('bypass_port'):
                kwargs['bypass_port'] = port_desc.bypass_port
            if port_desc.HasField('drywet_port'):
                kwargs['drywet_port'] = port_desc.drywet_port
            if port_desc.HasField('csound_instr'):
                kwargs['csound_instr'] = port_desc.csound_instr

            port = port_cls(description=port_desc, **kwargs)
            port.owner = self

            self.ports.append(port)
            if port_desc.direction == node_db.PortDescription.INPUT:
                self.inputs[port.name] = port
            else:
                self.outputs[port.name] = port

    @property
    def parent_nodes(self) -> List['Node']:
        parents = []  # type: List[Node]
        for port in self.inputs.values():
            for upstream_port in port.inputs:
                parents.append(upstream_port.owner)
        return parents

    async def setup(self) -> None:
        """Set up the node.

        Any expensive initialization should go here.
        """
        logger.info("%s: setup()", self.name)

        for port in self.ports:
            if isinstance(port, KRateControlInputPort):
                logger.info("Float control value '%s'", port.buf_name)
                cv = control_value.PyFloatControlValue(
                    port.buf_name, port.description.float_value.default, 1)
                self.__control_values[port.buf_name] = cv
                self.realm.add_active_control_value(cv)

    async def cleanup(self, deref: bool = False) -> None:
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def set_session_value(self, key: str, value: Any) -> None:
        pass

    @property
    def control_values(self) -> List[control_value.PyControlValue]:
        return [v for _, v in sorted(self.__control_values.items())]

    def add_to_spec_pre(self, spec: spec_lib.PySpec) -> None:
        for cv in self.control_values:
            spec.append_control_value(cv)

        for port in self.ports:
            spec.append_buffer(port.buf_name, port.get_buf_type())

            if port.buf_name in self.__control_values:
                spec.append_opcode(
                    'FETCH_CONTROL_VALUE', self.__control_values[port.buf_name], port.buf_name)
            elif isinstance(port, InputPortMixin):
                spec.append_opcode('CLEAR', port.buf_name)
                for upstream_port in port.inputs:
                    spec.append_opcode('MIX', upstream_port.buf_name, port.buf_name)

    def add_to_spec_post(self, spec: spec_lib.PySpec) -> None:
        pass


class ProcessorNode(Node):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__processor = None  # type: processor_lib.PyProcessor

    @property
    def processor(self) -> processor_lib.PyProcessor:
        assert self.__processor is not None
        return self.__processor

    async def setup(self) -> None:
        await super().setup()

        self.__processor = processor_lib.PyProcessor(
            self.realm.name, self.id, self._host_system, self.description)
        self.__processor.setup()
        self.realm.add_active_processor(self.__processor)

    async def cleanup(self, deref: bool = False) -> None:
        if self.__processor is not None:
            if deref:
                self.__processor = None
            else:
                self.__processor.cleanup()

        await super().cleanup(deref)

    def set_session_value(self, key: str, value: Any) -> None:
        if key == 'muted':
            self.__processor.handle_message(processor_message_pb2.ProcessorMessage(
                node_id=self.id,
                mute_node=processor_message_pb2.ProcessorMessage.MuteNode(muted=value)))

        super().set_session_value(key, value)

    def add_to_spec_pre(self, spec: spec_lib.PySpec) -> None:
        super().add_to_spec_pre(spec)

        spec.append_processor(self.__processor)

        for port_idx, port in enumerate(self.ports):
            spec.append_opcode('CONNECT_PORT', self.__processor, port_idx, port.buf_name)

        spec.append_opcode('CALL', self.__processor)


class PluginNode(ProcessorNode):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__plugin_host = None  # type: ipc.Stub
        self.__plugin_pipe_path = None  # type: str

    async def setup(self) -> None:
        await super().setup()

        self.__plugin_host = await self.realm.get_plugin_host()

        spec = plugin_host_pb2.PluginInstanceSpec()
        spec.realm = self.realm.name
        spec.node_id = self.id
        spec.node_description.CopyFrom(self.description)
        if self.initial_state is not None:
            spec.initial_state.CopyFrom(self.initial_state)
        self.__plugin_pipe_path = await self.__plugin_host.call(
            'CREATE_PLUGIN', spec, self.realm.callback_address)

        self.processor.set_parameters(
            processor_pb2.ProcessorParameters(
                plugin_pipe_path=self.__plugin_pipe_path))

    async def cleanup(self, deref: bool = False) -> None:
        await super().cleanup(deref)

        if self.__plugin_pipe_path is not None:
            await self.__plugin_host.call('DELETE_PLUGIN', self.realm.name, self.id)
            self.__plugin_pipe_path = None

        self.__plugin_host = None

    def add_to_spec_pre(self, spec: spec_lib.PySpec) -> None:
        super().add_to_spec_pre(spec)
        spec.append_buffer('%s:plugin_cond' % self.id, buffers.PyPluginCondBuffer())
        spec.append_opcode(
            'CONNECT_PORT', self.processor, len(self.ports), '%s:plugin_cond' % self.id)


class RealmSinkNode(Node):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id='sink', **kwargs)


class ChildRealmNode(Node):
    def __init__(self, *, child_realm: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__child_realm_name = child_realm
        self.__child_realm = None  # type: realm_lib.PyRealm

    async def setup(self) -> None:
        await super().setup()

        self.__child_realm = self.realm.child_realms[self.__child_realm_name]
        self.realm.add_active_child_realm(self.__child_realm)

    def add_to_spec_pre(self, spec: spec_lib.PySpec) -> None:
        super().add_to_spec_pre(spec)

        spec.append_child_realm(self.__child_realm)
        spec.append_opcode(
            'CALL_CHILD_REALM',
            self.__child_realm,
            self.outputs['out:left'].buf_name, self.outputs['out:right'].buf_name)


class Graph(object):
    def __init__(self, realm: realm_lib.PyRealm) -> None:
        self.__realm = realm
        self.__nodes = {}  # type: Dict[str, Node]

    @property
    def nodes(self) -> Set[Node]:
        return set(self.__nodes.values())

    def find_node(self, node_id: str) -> Node:
        return self.__nodes[node_id]

    def add_node(self, node: Node) -> None:
        if node.id in self.__nodes:
            raise GraphError("Duplicate node ID '%s'" % node.id)
        node.set_realm(self.__realm)

        self.__nodes[node.id] = node

    def remove_node(self, node: Node) -> None:
        if not node.is_owned_by(self.__realm):
            raise GraphError("Node has not been added to this realm")
        node.clear_realm()
        del self.__nodes[node.id]

    def compile(self, bpm: int, duration: audioproc.MusicalDuration) -> spec_lib.PySpec:
        spec = spec_lib.PySpec()
        spec.bpm = bpm
        spec.duration = duration

        sorted_nodes = toposort.toposort_flatten(
            {node: set(node.parent_nodes) for node in self.__nodes.values()},
            sort=False)

        for node in sorted_nodes:
            node.add_to_spec_pre(spec)
            node.add_to_spec_post(spec)

        return spec
