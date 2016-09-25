#!/usr/bin/python3

import logging

import numpy

from noisicaa import core
from noisicaa import audioproc

from .track import Track
from .time import Duration
from . import model
from . import state
from . import commands
from . import mutations
from . import track
from . import pipeline_graph
from . import misc
from . import time_mapper

logger = logging.getLogger(__name__)


class SampleRef(model.SampleRef, state.StateBase):
    def __init__(self, timepos=None, sample_id=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.timepos = timepos
            self.sample_id = sample_id

state.StateBase.register_class(SampleRef)


class SampleEntitySource(track.EntitySource):
    def __init__(self, track):
        super().__init__(track)

        self.time_mapper = time_mapper.TimeMapper(self._sheet)

    def get_entities(self, frame_data, sample_pos_offset):
        # entity = audioproc.ControlFrameEntity()

        # if len(self._track.points) > 0:
        #     sample_pos = frame_data.sample_pos - sample_pos_offset

        #     timepos = self.time_mapper.sample2timepos(
        #         sample_pos % self.time_mapper.total_duration_samples)
        #     for point in self._track.points:
        #         if timepos <= point.timepos:
        #             if point.is_first:
        #                 entity.frame = numpy.full(
        #                     frame_data.duration, point.value, dtype=numpy.float32)
        #             else:
        #                 prev = point.prev_sibling

        #                 # TODO: don't use a constant value per frame,
        #                 # compute control value at a-rate.
        #                 value = (
        #                     prev.value
        #                     + (timepos - prev.timepos)
        #                     * (point.value - prev.value)
        #                     / (point.timepos - prev.timepos))
        #                 entity.frame = numpy.full(
        #                     frame_data.duration, value, dtype=numpy.float32)
        #             break
        #     else:
        #         entity.frame = numpy.full(
        #             frame_data.duration, self._track.points[-1].value, dtype=numpy.float32)

        # else:
        #     entity.frame = numpy.zeros(frame_data.duration, dtype=numpy.float32)

        # frame_data.entities['track:%s' % self._track.id] = entity
        pass


class SampleTrack(model.SampleTrack, Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_entity_source(self):
        return SampleEntitySource(self)

    @property
    def mixer_name(self):
        return self.parent_mixer_name

    @property
    def mixer_node(self):
        return self.parent_mixer_node

    @property
    def audio_source_name(self):
        return '%s-control' % self.id

    @property
    def audio_source_node(self):
        if self.audio_source_id is None:
            raise ValueError("No audio source node found.")

        return self.root.get_object(self.audio_source_id)

    def add_pipeline_nodes(self):
        audio_source_node = pipeline_graph.AudioSourcePipelineGraphNode(
            name="Audio Source",
            graph_pos=self.parent_mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(audio_source_node)
        self.audio_source_id = audio_source_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            audio_source_node, 'out', self.mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.audio_source_node)
        self.audio_source_id = None


state.StateBase.register_class(SampleTrack)
