#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa import node_db

from . import model
from . import state
from . import commands
from . import mutations
from . import misc

logger = logging.getLogger(__name__)


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


class SetPipelineGraphNodeParameter(commands.Command):
    parameter_name = core.Property(str)
    float_value = core.Property(float, allow_none=True)

    def __init__(self, parameter_name=None, float_value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.parameter_name = parameter_name
            self.float_value = float_value

    def run(self, node):
        assert isinstance(node, BasePipelineGraphNode)

        parameter = node.description.get_parameter(self.parameter_name)
        if parameter.param_type == node_db.ParameterType.Float:
            assert self.float_value is not None
            node.set_parameter(
                parameter.name,
                parameter.validate(self.float_value))

commands.Command.register_command(SetPipelineGraphNodeParameter)

class SetPipelineGraphPortParameter(commands.Command):
    port_name = core.Property(str)
    muted = core.Property(bool, allow_none=True)
    volume = core.Property(float, allow_none=True)
    bypass = core.Property(bool, allow_none=True)
    drywet = core.Property(float, allow_none=True)

    def __init__(
            self, port_name=None,
            muted=None, volume=None,
            bypass=None, drywet=None,
            state=None):
        super().__init__(state=state)
        if state is None:
            self.port_name = port_name
            self.muted = muted
            self.volume = volume
            self.bypass = bypass
            self.drywet = drywet

    def run(self, node):
        assert isinstance(node, BasePipelineGraphNode)

        node.set_port_parameters(
            self.port_name,
            muted=self.muted, volume=self.volume,
            bypass=self.bypass, drywet=self.drywet)

commands.Command.register_command(SetPipelineGraphPortParameter)


class PipelineGraphNodeParameterValue(
        model.PipelineGraphNodeParameterValue, state.StateBase):
    def __init__(self, name=None, value=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.name = name
            self.value = value

state.StateBase.register_class(PipelineGraphNodeParameterValue)


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
    def sheet(self):
        return self.parent

    @property
    def project(self):
        return self.sheet.project

    @property
    def pipeline_node_id(self):
        raise NotImplementedError

    def add_to_pipeline(self):
        raise NotImplementedError

    def set_initial_parameters(self):
        parameter_values = dict(
            (p.name, p.value) for p in self.parameter_values)

        params = {}
        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                params[parameter.name] = parameter_values.get(
                    parameter.name, parameter.default)

        if params:
            self.sheet.handle_pipeline_mutation(
                mutations.SetNodeParameter(self.pipeline_node_id, **params))

        for port in self.description.ports:
            if port.direction != node_db.PortDirection.Output:
                continue

            port_property_values = dict(
                (p.name, p.value) for p in self.port_property_values
                if p.port_name == port.name)

            if port_property_values:
                self.sheet.handle_pipeline_mutation(
                    mutations.SetPortProperty(
                        self.pipeline_node_id, port.name,
                        **port_property_values))

    def remove_from_pipeline(self):
        raise NotImplementedError

    def set_parameter(self, parameter_name, value):
        for param_value in self.parameter_values:
            if param_value.name == parameter_name:
                param_value.value = value
                break
        else:
            self.parameter_values.append(PipelineGraphNodeParameterValue(
                name=parameter_name, value=value))

        self.sheet.handle_pipeline_mutation(
            mutations.SetNodeParameter(
                self.pipeline_node_id,
                **{parameter_name: value}))

    def set_port_parameters(self, port_name, muted=None, volume=None, bypass=None, drywet=None):
        for prop_name, value in (
                ('muted', muted), ('volume', volume),
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

        self.sheet.handle_pipeline_mutation(
            mutations.SetPortProperty(
                self.pipeline_node_id, port_name,
                muted=muted, volume=volume,
                bypass=bypass, drywet=drywet))


class PipelineGraphNode(model.PipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, node_uri=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.node_uri = node_uri

    @property
    def pipeline_node_id(self):
        return self.id

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                self.description.node_cls,
                self.pipeline_node_id,
                self.name,
                description=self.description))

        self.set_initial_parameters()

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(PipelineGraphNode)


class AudioOutPipelineGraphNode(
        model.AudioOutPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    @property
    def pipeline_node_id(self):
        return 'sink'

    def add_to_pipeline(self):
        # Nothing to do, predefined node of the pipeline.
        pass

    def remove_from_pipeline(self):
        # Nothing to do, predefined node of the pipeline.
        pass

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

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'passthru', self.pipeline_node_id, self.name))
        self.sheet.handle_pipeline_mutation(
            mutations.SetPortProperty(
                self.pipeline_node_id, 'out',
                muted=self.track.muted, volume=self.track.volume))

        self.set_initial_parameters()

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(TrackMixerPipelineGraphNode)


class ControlSourcePipelineGraphNode(
        model.ControlSourcePipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.control_source_name

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'track_control_source', self.pipeline_node_id, self.name,
                entity_name='track:%s' % self.track.id))

        self.set_initial_parameters()

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(ControlSourcePipelineGraphNode)


class EventSourcePipelineGraphNode(
        model.EventSourcePipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.event_source_name

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'track_event_source', self.pipeline_node_id, self.name,
                queue_name='track:%s' % self.track.id))

        self.set_initial_parameters()

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(EventSourcePipelineGraphNode)


class InstrumentPipelineGraphNode(
        model.InstrumentPipelineGraphNode, BasePipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.instr_name

    def update_pipeline(self):
        connections = []
        for connection in self.sheet.pipeline_graph_connections:
            if connection.source_node is self or connection.dest_node is self:
                connections.append(connection)

        for connection in connections:
            connection.remove_from_pipeline()
        self.remove_from_pipeline()
        self.add_to_pipeline()
        for connection in connections:
            connection.add_to_pipeline()

    def add_to_pipeline(self):
        instr = self.track.instrument

        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'fluidsynth', self.pipeline_node_id, self.name,
                soundfont_path=instr.path,
                bank=instr.bank,
                preset=instr.preset))

        self.set_initial_parameters()

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

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

    @property
    def sheet(self):
        return self.parent

    @property
    def project(self):
        return self.sheet.project

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.ConnectPorts(
                self.source_node.pipeline_node_id, self.source_port,
                self.dest_node.pipeline_node_id, self.dest_port))

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.DisconnectPorts(
                self.source_node.pipeline_node_id, self.source_port,
                self.dest_node.pipeline_node_id, self.dest_port))

state.StateBase.register_class(PipelineGraphConnection)
