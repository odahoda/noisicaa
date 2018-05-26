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

#import io
import logging
#from xml.etree import ElementTree
from typing import cast, Any, Optional, Union, Iterator, List  # pylint: disable=unused-import

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import instrument_db
from noisicaa import node_db
from noisicaa import model
from . import pmodel
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class PresetLoadError(Exception):
    pass

class NotAPresetError(PresetLoadError):
    pass


class SetPipelineGraphNodePos(commands.Command):
    proto_type = 'set_pipeline_graph_node_pos'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetPipelineGraphNodePos, pb)
        node = down_cast(pmodel.BasePipelineGraphNode, pool[self.proto.command.target])

        node.graph_pos = model.Pos2F.from_proto(pb.graph_pos)

commands.Command.register_command(SetPipelineGraphNodePos)


class SetPipelineGraphControlValue(commands.Command):
    proto_type = 'set_pipeline_graph_control_value'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetPipelineGraphControlValue, pb)
        node = down_cast(pmodel.BasePipelineGraphNode, pool[self.proto.command.target])

        port = node_db.get_port(node.description, pb.port_name)
        assert port.direction == node_db.PortDescription.INPUT
        assert port.type == node_db.PortDescription.KRATE_CONTROL

        node.set_control_value(port.name, pb.float_value, pb.generation)

commands.Command.register_command(SetPipelineGraphControlValue)


class SetPipelineGraphPluginState(commands.Command):
    proto_type = 'set_pipeline_graph_plugin_state'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetPipelineGraphPluginState, pb)
        node = down_cast(pmodel.BasePipelineGraphNode, pool[self.proto.command.target])

        node.set_plugin_state(pb.plugin_state)

commands.Command.register_command(SetPipelineGraphPluginState)


class PipelineGraphNodeToPreset(commands.Command):
    proto_type = 'pipeline_graph_node_to_preset'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> bytes:
        pb = down_cast(commands_pb2.PipelineGraphNodeToPreset, pb)
        node = down_cast(pmodel.PipelineGraphNode, pool[self.proto.command.target])

        return node.to_preset()

commands.Command.register_command(PipelineGraphNodeToPreset)


class PipelineGraphNodeFromPreset(commands.Command):
    proto_type = 'pipeline_graph_node_from_preset'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.PipelineGraphNodeFromPreset, pb)
        node = down_cast(pmodel.PipelineGraphNode, pool[self.proto.command.target])

        node.from_preset(pb.preset)

commands.Command.register_command(PipelineGraphNodeFromPreset)


class PipelineGraphControlValue(pmodel.PipelineGraphControlValue):
    def create(
            self, *,
            name: Optional[str] = None,
            value: Optional[float] = None, generation: Optional[int] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.name = name
        self.value = model.ControlValue(value=value, generation=generation)


class BasePipelineGraphNode(pmodel.BasePipelineGraphNode):  # pylint: disable=abstract-method
    def create(
            self, *,
            name: Optional[str] = None, graph_pos: model.Pos2F = model.Pos2F(0, 0),
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.name = name
        self.graph_pos = graph_pos

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        for port in self.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                for cv in self.control_values:
                    if cv.name == port.name:
                        yield audioproc.SetControlValue(
                            '%s:%s' % (self.pipeline_node_id, cv.name),
                            cv.value.value, cv.value.generation)

    def set_control_value(self, port_name: str, value: float, generation: int) -> None:
        for control_value in self.control_values:
            if control_value.name == port_name:
                if generation < control_value.value.generation:
                    return
                control_value.value = model.ControlValue(value=value, generation=generation)
                break
        else:
            self.control_values.append(self._pool.create(
                PipelineGraphControlValue,
                name=port_name, value=value, generation=generation))

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.SetControlValue(
                    '%s:%s' % (self.pipeline_node_id, port_name),
                    value, generation))

    def set_plugin_state(self, plugin_state: audioproc.PluginState) -> None:
        self.plugin_state = plugin_state

        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                audioproc.SetPluginState(self.pipeline_node_id, plugin_state))


class PipelineGraphNode(pmodel.PipelineGraphNode, BasePipelineGraphNode):
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

    @property
    def pipeline_node_id(self) -> str:
        return '%016x' % self.id

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name,
            initial_state=self.plugin_state)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class AudioOutPipelineGraphNode(pmodel.AudioOutPipelineGraphNode, BasePipelineGraphNode):
    @property
    def pipeline_node_id(self) -> str:
        return 'sink'

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        # Nothing to do, predefined node of the pipeline.
        yield from []


class TrackMixerPipelineGraphNode(pmodel.TrackMixerPipelineGraphNode, BasePipelineGraphNode):
    def create(self, *, track: Optional[pmodel.Track] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.track = track

    @property
    def pipeline_node_id(self) -> str:
        return self.track.mixer_name

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class CVGeneratorPipelineGraphNode(pmodel.CVGeneratorPipelineGraphNode, BasePipelineGraphNode):
    def create(self, *, track: Optional[pmodel.Track] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.track = track

    @property
    def pipeline_node_id(self) -> str:
        return down_cast(pmodel.ControlTrack, self.track).generator_name

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class SampleScriptPipelineGraphNode(pmodel.SampleScriptPipelineGraphNode, BasePipelineGraphNode):
    def create(self, *, track: Optional[pmodel.Track] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.track = track

    @property
    def pipeline_node_id(self) -> str:
        return down_cast(pmodel.SampleTrack, self.track).sample_script_name

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class PianoRollPipelineGraphNode(pmodel.PianoRollPipelineGraphNode, BasePipelineGraphNode):
    def create(self, *, track: Optional[pmodel.Track] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.track = track

    @property
    def pipeline_node_id(self) -> str:
        return cast(Union[pmodel.ScoreTrack, pmodel.BeatTrack], self.track).event_source_name

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class InstrumentPipelineGraphNode(pmodel.InstrumentPipelineGraphNode, BasePipelineGraphNode):
    def create(self, *, track: Optional[pmodel.Track] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.track = track

    @property
    def pipeline_node_id(self) -> str:
        return cast(Union[pmodel.ScoreTrack, pmodel.BeatTrack], self.track).instr_name

    def get_update_mutations(self) -> Iterator[audioproc.Mutation]:
        connections = []  # type: List[pmodel.PipelineGraphConnection]
        for connection in self.project.pipeline_graph_connections:
            if connection.source_node is self or connection.dest_node is self:
                connections.append(connection)

        for connection in connections:
            yield from connection.get_remove_mutations()
        yield from self.get_remove_mutations()
        yield from self.get_add_mutations()
        for connection in connections:
            yield from connection.get_add_mutations()

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        node_description = instrument_db.parse_uri(
            cast(Union[pmodel.ScoreTrack, pmodel.BeatTrack], self.track).instrument,
            self.project.get_node_description)
        yield audioproc.AddNode(
            description=node_description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)


class PipelineGraphConnection(pmodel.PipelineGraphConnection):
    def create(
            self, *,
            source_node: Optional[BasePipelineGraphNode] = None,
            source_port: Optional[str] = None,
            dest_node: Optional[BasePipelineGraphNode] = None,
            dest_port: Optional[str] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.source_node = source_node
        self.source_port = source_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.ConnectPorts(
            self.source_node.pipeline_node_id, self.source_port,
            self.dest_node.pipeline_node_id, self.dest_port)

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.DisconnectPorts(
            self.source_node.pipeline_node_id, self.source_port,
            self.dest_node.pipeline_node_id, self.dest_port)
