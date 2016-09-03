#!/usr/bin/python3

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import pipeline_graph
from . import misc

logger = logging.getLogger(__name__)


class UpdateTrackProperties(commands.Command):
    name = core.Property(str, allow_none=True)
    visible = core.Property(bool, allow_none=True)
    muted = core.Property(bool, allow_none=True)
    volume = core.Property(float, allow_none=True)

    # TODO: this only applies to ScoreTrack... use separate command for
    #   class specific properties?
    transpose_octaves = core.Property(int, allow_none=True)

    def __init__(self, name=None, visible=None, muted=None, volume=None,
                 transpose_octaves=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.visible = visible
            self.muted = muted
            self.volume = volume
            self.transpose_octaves = transpose_octaves

    def run(self, track):
        assert isinstance(track, Track)

        if self.name is not None:
            track.name = self.name

        if self.visible is not None:
            track.visible = self.visible

        if self.muted is not None:
            track.muted = self.muted
            track.sheet.handle_pipeline_mutation(
                mutations.SetPortProperty(
                    track.mixer_name, 'out', muted=track.muted))

        if self.volume is not None:
            track.volume = self.volume
            track.sheet.handle_pipeline_mutation(
                mutations.SetPortProperty(
                    track.mixer_name, 'out', volume=track.volume))

        if self.transpose_octaves is not None:
            track.transpose_octaves = self.transpose_octaves

commands.Command.register_command(UpdateTrackProperties)


class Measure(model.Measure, state.StateBase):
    def __init__(self, state=None):
        super().__init__(state)

    @property
    def empty(self):
        return False


class MeasureReference(model.MeasureReference, state.StateBase):
    def __init__(self, measure=None, state=None):
        super().__init__(state)

        if state is None:
            self.measure = measure

state.StateBase.register_class(MeasureReference)


class EventSource(object):
    def __init__(self, track):
        self._track = track
        self._sheet = track.sheet

    def get_events(self, start_sample_pos, end_sample_pos):
        raise NotImplementedError


class Track(model.Track, state.StateBase):
    measure_cls = None

    def __init__(self, name=None, state=None):
        super().__init__(state)

        if state is None:
            self.name = name

    @property
    def project(self):
        return self.sheet.project

    def append_measure(self):
        self.insert_measure(-1)

    def insert_measure(self, idx):
        assert idx == -1 or (0 <= idx <= len(self.measure_list) - 1)

        if idx == -1:
            idx = len(self.measure_list)

        if idx == 0 and len(self.measure_list) > 0:
            ref = self.measure_list[0].measure
        elif idx > 0:
            ref = self.measure_list[idx-1].measure
        else:
            ref = None
        measure = self.create_empty_measure(ref)
        self.measure_heap.append(measure)
        self.measure_list.insert(idx, MeasureReference(measure=measure))

    def remove_measure(self, idx):
        measure = self.measure_list[idx].measure
        assert measure.ref_count > 0

        self.measure_list[idx].measure = None
        del self.measure_list[idx]

        if measure.ref_count == 0:
            logger.info("GC measure %s", measure.id)
            del self.measure_heap[measure.index]

    def create_empty_measure(self, ref):  # pylint: disable=unused-argument
        return self.measure_cls()  # pylint: disable=not-callable

    @property
    def parent_mixer_name(self):
        return self.parent.mixer_name

    @property
    def parent_mixer_node(self):
        return self.parent.mixer_node

    @property
    def mixer_name(self):
        return '%s-track-mixer' % self.id

    @property
    def mixer_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.TrackMixerPipelineGraphNode) and node.track is self:
                return node

        raise ValueError("No mixer node found.")

    @property
    def relative_position_to_parent_mixer(self):
        return misc.Pos2F(-200, self.index * 100)

    @property
    def default_mixer_name(self):
        return "Track Mixer"

    def add_pipeline_nodes(self):
        parent_mixer_node = self.parent_mixer_node

        mixer_node = pipeline_graph.TrackMixerPipelineGraphNode(
            name=self.default_mixer_name,
            graph_pos=(
                parent_mixer_node.graph_pos
                + self.relative_position_to_parent_mixer),
            track=self)
        self.sheet.add_pipeline_graph_node(mixer_node)

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out', parent_mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.mixer_node)
