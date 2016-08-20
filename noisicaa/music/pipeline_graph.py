#!/usr/bin/python3

import logging

from noisicaa import core

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
        assert isinstance(node, PipelineGraphNode)

        node.graph_pos = self.graph_pos

commands.Command.register_command(SetPipelineGraphNodePos)


class PipelineGraphNode(model.PipelineGraphNode, state.StateBase):
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
        pass

    def remove_from_pipeline(self):
        pass

state.StateBase.register_class(PipelineGraphNode)


class AudioOutPipelineGraphNode(
        model.AudioOutPipelineGraphNode, PipelineGraphNode):
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
        model.TrackMixerPipelineGraphNode, PipelineGraphNode):
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

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(TrackMixerPipelineGraphNode)


class EventSourcePipelineGraphNode(
        model.EventSourcePipelineGraphNode, PipelineGraphNode):
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

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(EventSourcePipelineGraphNode)


class InstrumentPipelineGraphNode(
        model.InstrumentPipelineGraphNode, PipelineGraphNode):
    def __init__(self, track=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.track = track

    @property
    def pipeline_node_id(self):
        return self.track.instr_name

    def add_to_pipeline(self):
        instr = self.track.instrument

        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'fluidsynth', self.pipeline_node_id, self.name,
                soundfont_path=instr.path,
                bank=instr.bank,
                preset=instr.preset))

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
        pass

state.StateBase.register_class(PipelineGraphConnection)
