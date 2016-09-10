#!/usr/bin/python3

import logging

from noisicaa import core

from .track import Track
from .time import Duration
from . import model
from . import state
from . import commands
from . import mutations

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


class ControlTrack(model.ControlTrack, Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.points.append(ControlPoint(timepos=Duration(0, 4), value=0.0))
            self.points.append(ControlPoint(timepos=Duration(1, 4), value=1.0))
            self.points.append(ControlPoint(timepos=Duration(2, 4), value=0.0))
            self.points.append(ControlPoint(timepos=Duration(3, 4), value=1.0))
            self.points.append(ControlPoint(timepos=Duration(4, 4), value=0.0))

    @property
    def mixer_name(self):
        return self.parent_mixer_name

    @property
    def mixer_node(self):
        return self.parent_mixer_node

    def add_pipeline_nodes(self):
        pass

    def remove_pipeline_nodes(self):
        pass

state.StateBase.register_class(ControlTrack)
