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

    def add_to_pipeline(self):
        super().add_to_pipeline()
        for track in self.tracks:
            track.add_to_pipeline()

    def remove_from_pipeline(self):
        for track in self.tracks:
            track.remove_from_pipeline()
        super().remove_from_pipeline()

state.StateBase.register_class(TrackGroup)


class MasterTrackGroup(model.MasterTrackGroup, TrackGroup):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    @property
    def parent_mixer_name(self):
        return 'sink'

    @property
    def mixer_name(self):
        return '%s-master-mixer' % self.id

state.StateBase.register_class(MasterTrackGroup)
