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
