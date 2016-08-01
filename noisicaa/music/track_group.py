#!/usr/bin/python3

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import track

logger = logging.getLogger(__name__)


class TrackGroup(model.TrackGroup, track.Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

state.StateBase.register_class(TrackGroup)
