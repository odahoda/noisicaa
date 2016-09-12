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


class AddControlPoint(commands.Command):
    timepos = core.Property(Duration)
    value = core.Property(float)

    def __init__(self, timepos=None, value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.timepos = timepos
            self.value = value

    def run(self, track):
        assert isinstance(track, ControlTrack)

        for insert_index, point in enumerate(track.points):
            if point.timepos == self.timepos:
                raise ValueError("Duplicate control point")
            if point.timepos > self.timepos:
                break
        else:
            insert_index = len(track.points)

        track.points.insert(
            insert_index,
            ControlPoint(timepos=self.timepos, value=self.value))

commands.Command.register_command(AddControlPoint)


class RemoveControlPoint(commands.Command):
    point_id = core.Property(str)

    def __init__(self, point_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.point_id = point_id

    def run(self, track):
        assert isinstance(track, ControlTrack)

        root = track.root
        point = root.get_object(self.point_id)
        assert point.is_child_of(track)

        del track.points[point.index]

commands.Command.register_command(RemoveControlPoint)


class MoveControlPoint(commands.Command):
    point_id = core.Property(str)
    timepos = core.Property(Duration, allow_none=True)
    value = core.Property(float, allow_none=True)

    def __init__(self, point_id=None, timepos=None, value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.point_id = point_id
            self.timepos = timepos
            self.value = value

    def run(self, track):
        assert isinstance(track, ControlTrack)

        root = track.root
        point = root.get_object(self.point_id)
        assert point.is_child_of(track)

        if self.timepos is not None:
            if not point.is_first:
                if self.timepos <= point.prev_sibling.timepos:
                    raise ValueError("Control point out of order.")
            else:
                if self.timepos < Duration(0, 4):
                    raise ValueError("Control point out of order.")

            if not point.is_last:
                if self.timepos >= point.next_sibling.timepos:
                    raise ValueError("Control point out of order.")

            point.timepos = self.timepos

        if self.value is not None:
            # TODO: check that value is in valid range.
            point.value = self.value

commands.Command.register_command(MoveControlPoint)


class ControlPoint(model.ControlPoint, state.StateBase):
    def __init__(self, timepos=None, value=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.timepos = timepos
            self.value = value

state.StateBase.register_class(ControlPoint)


class ControlEntitySource(track.EntitySource):
    def __init__(self, track):
        super().__init__(track)

        self.time_mapper = time_mapper.TimeMapper(self._sheet)

    def get_entities(self, frame_data, sample_pos_offset):
        entity = audioproc.ControlFrameEntity()

        if len(self._track.points) > 0:
            sample_pos = frame_data.sample_pos - sample_pos_offset

            timepos = self.time_mapper.sample2timepos(
                sample_pos % self.time_mapper.total_duration_samples)
            for point in self._track.points:
                if timepos <= point.timepos:
                    if point.is_first:
                        entity.frame = numpy.full(
                            frame_data.duration, point.value, dtype=numpy.float32)
                    else:
                        prev = point.prev_sibling

                        # TODO: don't use a constant value per frame,
                        # compute control value at a-rate.
                        value = (
                            prev.value
                            + (timepos - prev.timepos)
                            * (point.value - prev.value)
                            / (point.timepos - prev.timepos))
                        entity.frame = numpy.full(
                            frame_data.duration, value, dtype=numpy.float32)
                    break
            else:
                entity.frame = numpy.full(
                    frame_data.duration, self._track.points[-1].value, dtype=numpy.float32)

        else:
            entity.frame = numpy.zeros(frame_data.duration, dtype=numpy.float32)

        frame_data.entities['track:%s' % self._track.id] = entity


class ControlTrack(model.ControlTrack, Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_entity_source(self):
        return ControlEntitySource(self)

    @property
    def mixer_name(self):
        return self.parent_mixer_name

    @property
    def mixer_node(self):
        return self.parent_mixer_node

    @property
    def control_source_name(self):
        return '%s-control' % self.id

    @property
    def control_source_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if (isinstance(node, pipeline_graph.ControlSourcePipelineGraphNode)
                    and node.track is self):
                return node

        raise ValueError("No control source node found.")

    def add_pipeline_nodes(self):
        control_source_node = pipeline_graph.ControlSourcePipelineGraphNode(
            name="Control Value",
            graph_pos=self.parent_mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(control_source_node)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.control_source_node)


state.StateBase.register_class(ControlTrack)
