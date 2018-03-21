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

# TODO: pylint-unclean

import io
import logging
from xml.etree import ElementTree

from noisicaa import audioproc
from noisicaa import instrument_db
from noisicaa import core
from noisicaa import node_db

from . import model
from . import state
from . import commands
from . import misc

logger = logging.getLogger(__name__)


class PresetLoadError(Exception):
    pass

class NotAPresetError(PresetLoadError):
    pass


class SetPipelineGraphNodePos(commands.Command):
    graph_pos = core.Property(misc.Pos2F)

    def __init__(self, graph_pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.graph_pos = graph_pos

    def run(self, node):
        assert isinstance(node, BasePipelineGraphNode)

        node.graph_pos = self.graph_pos

commands.Command.register_command(SetPipelineGraphNodePos)


class SetPipelineGraphControlValue(commands.Command):
    port_name = core.Property(str)
    float_value = core.Property(float, allow_none=True)

    def __init__(self, port_name=None, float_value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.port_name = port_name
            self.float_value = float_value

    def run(self, node):
        assert isinstance(node, BasePipelineGraphNode)

        port = node_db.get_port(node.description, self.port_name)
        assert port.direction == node_db.PortDescription.INPUT
        assert port.type == node_db.PortDescription.KRATE_CONTROL
        assert self.float_value is not None

        node.set_control_value(port.name, self.float_value)

commands.Command.register_command(SetPipelineGraphControlValue)


class SetPipelineGraphPortParameter(commands.Command):
    port_name = core.Property(str)
    bypass = core.Property(bool, allow_none=True)
    drywet = core.Property(float, allow_none=True)

    def __init__(
            self, port_name=None,
            bypass=None, drywet=None,
            state=None):
        super().__init__(state=state)
        if state is None:
            self.port_name = port_name
            self.bypass = bypass
            self.drywet = drywet

    def run(self, node):
        assert isinstance(node, BasePipelineGraphNode)

        node.set_port_parameters(
            self.port_name,
            bypass=self.bypass, drywet=self.drywet)

commands.Command.register_command(SetPipelineGraphPortParameter)


class PipelineGraphNodeToPreset(commands.Command):
    def __init__(self, state=None):
        super().__init__(state=state)

    def run(self, node):
        assert isinstance(node, PipelineGraphNode)

        return node.to_preset()

commands.Command.register_command(PipelineGraphNodeToPreset)


class PipelineGraphNodeFromPreset(commands.Command):
    preset = core.Property(bytes)

    def __init__(self, preset=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.preset = preset

    def run(self, node):
        assert isinstance(node, PipelineGraphNode)

        return node.from_preset(self.preset)

commands.Command.register_command(PipelineGraphNodeFromPreset)


class PipelineGraphControlValue(
        model.PipelineGraphControlValue, state.StateBase):
    def __init__(self, name=None, value=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.name = name
            self.value = value

state.StateBase.register_class(PipelineGraphControlValue)


class PipelineGraphPortPropertyValue(
        model.PipelineGraphPortPropertyValue, state.StateBase):
    def __init__(
            self, port_name=None, name=None, value=None,
            state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.port_name = port_name
            self.name = name
            self.value = value

state.StateBase.register_class(PipelineGraphPortPropertyValue)


class BasePipelineGraphNode(model.BasePipelineGraphNode, state.StateBase):
    def __init__(self, name=None, graph_pos=misc.Pos2F(0, 0), state=None):
        super().__init__(state)

        if state is None:
            self.name = name
            self.graph_pos = graph_pos

    @property
    def pipeline_node_id(self):
        raise NotImplementedError

    def get_add_mutations(self):
        raise NotImplementedError

    def get_initial_parameter_mutations(self):
        for port in self.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                and port.type == node_db.PortDescription.KRATE_CONTROL):
                for cv in self.control_values:
                    yield audioproc.SetControlValue(
                        '%s:%s' % (self.pipeline_node_id, cv.name), cv.value)

            elif port.direction == node_db.PortDescription.OUTPUT:
                port_property_values = dict(
                    (p.name, p.value) for p in self.port_property_values
                    if p.port_name == port.name)

                if port_property_values:
                    yield audioproc.SetPortProperty(
                        self.pipeline_node_id, port.name,
                        **port_property_values)

    def get_remove_mutations(self):
        raise NotImplementedError

    def set_port_parameters(self, port_name, bypass=None, drywet=None):
        for prop_name, value in (
                ('bypass', bypass), ('drywet', drywet)):
            if value is None:
                continue

            for prop_value in self.port_property_values:
                if (prop_value.port_name == port_name
                    and prop_value.name == prop_name):
                    prop_value.value = value
                    break
            else:
                self.port_property_values.append(
                    PipelineGraphPortPropertyValue(
                        port_name=port_name, name=prop_name, value=value))

        if self.attached_to_root:
            self.project.handle_pipeline_mutation(
                audioproc.SetPortProperty(
                    self.pipeline_node_id, port_name,
                    bypass=bypass, drywet=drywet))

    def set_control_value(self, port_name, value):
        for control_value in self.control_values:
            if control_value.name == port_name:
                control_value.value = value
                break
        else:
            self.control_values.append(PipelineGraphControlValue(
                name=port_name, value=value))

        if self.attached_to_root:
            self.project.handle_pipeline_mutation(
                audioproc.SetControlValue('%s:%s' % (self.pipeline_node_id, port_name), value))


class PipelineGraphNode(model.PipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, node_uri=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.node_uri = node_uri

    def to_preset(self):
        doc = ElementTree.Element('preset', version='1')
        doc.text = '\n'
        doc.tail = '\n'

        display_name_elem = ElementTree.SubElement(doc, 'display-name')
        display_name_elem.text = "User preset"
        display_name_elem.tail = '\n'

        node_uri_elem = ElementTree.SubElement(doc, 'node', uri=self.node_uri)
        node_uri_elem.tail = '\n'

        tree = ElementTree.ElementTree(doc)
        buf = io.BytesIO()
        tree.write(buf, encoding='utf-8', xml_declaration=True)
        return buf.getvalue()

    def from_preset(self, xml):
        preset = node_db.Preset.parse(io.BytesIO(xml), self.project.get_node_description)

        if preset.node_uri != self.node_uri:
            raise node_db.PresetLoadError(
                "Mismatching node_uri (Expected %s, got %s)."
                % (self.node_uri, preset.node_uri))

    @property
    def pipeline_node_id(self):
        return self.id

    def get_add_mutations(self):
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(PipelineGraphNode)


class AudioOutPipelineGraphNode(
        model.AudioOutPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    @property
    def pipeline_node_id(self):
        return 'sink'

    def get_add_mutations(self):
        # Nothing to do, predefined node of the pipeline.
        return []

    def get_remove_mutations(self):
        # Nothing to do, predefined node of the pipeline.
        return []

state.StateBase.register_class(AudioOutPipelineGraphNode)


class TrackMixerPipelineGraphNode(
        model.TrackMixerPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.mixer_name

    def get_add_mutations(self):
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(TrackMixerPipelineGraphNode)


class CVGeneratorPipelineGraphNode(model.CVGeneratorPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.generator_name

    def get_add_mutations(self):
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(CVGeneratorPipelineGraphNode)


class SampleScriptPipelineGraphNode(model.SampleScriptPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.sample_script_name

    def get_add_mutations(self):
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(SampleScriptPipelineGraphNode)


class PianoRollPipelineGraphNode(model.PianoRollPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.event_source_name

    def get_add_mutations(self):
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(PianoRollPipelineGraphNode)


class InstrumentPipelineGraphNode(
        model.InstrumentPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.instr_name

    def get_update_mutations(self):
        connections = []
        for connection in self.project.pipeline_graph_connections:
            if connection.source_node is self or connection.dest_node is self:
                connections.append(connection)

        for connection in connections:
            yield from connection.get_remove_mutations()
        yield from self.get_remove_mutations()
        yield from self.get_add_mutations()
        for connection in connections:
            yield from connection.get_add_mutations()

    def get_add_mutations(self):
        node_description = instrument_db.parse_uri(
            self.track.instrument, self.project.get_node_description)
        yield audioproc.AddNode(
            description=node_description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self):
        yield audioproc.RemoveNode(self.pipeline_node_id)

state.StateBase.register_class(InstrumentPipelineGraphNode)


class PipelineGraphConnection(
        model.PipelineGraphConnection, state.StateBase):
    def __init__(self, source_node=None, source_port=None, dest_node=None, dest_port=None, state=None):
        super().__init__(state)

        if state is None:
            self.source_node = source_node
            self.source_port = source_port
            self.dest_node = dest_node
            self.dest_port = dest_port

    def get_add_mutations(self):
        yield audioproc.ConnectPorts(
            self.source_node.pipeline_node_id, self.source_port,
            self.dest_node.pipeline_node_id, self.dest_port)

    def get_remove_mutations(self):
        yield audioproc.DisconnectPorts(
            self.source_node.pipeline_node_id, self.source_port,
            self.dest_node.pipeline_node_id, self.dest_port)

state.StateBase.register_class(PipelineGraphConnection)
