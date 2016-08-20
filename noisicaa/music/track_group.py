#!/usr/bin/python3

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import track
from . import misc

logger = logging.getLogger(__name__)


class TrackGroup(model.TrackGroup, track.Track):
    def __init__(self, state=None, num_measures=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()
        for track in self.tracks:
            track.add_pipeline_nodes()

    def remove_pipeline_nodes(self):
        for track in self.tracks:
            track.remove_pipeline_nodes()
        super().remove_pipeline_nodes()

state.StateBase.register_class(TrackGroup)


class MasterTrackGroup(model.MasterTrackGroup, TrackGroup):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    @property
    def parent_mixer_name(self):
        return 'sink'

    @property
    def parent_mixer_node(self):
        return self.sheet.audio_out_node

    @property
    def relative_position_to_parent_mixer(self):
        return misc.Pos2F(-200, 0)

    @property
    def default_mixer_name(self):
        return "Group Mixer"

    @property
    def mixer_name(self):
        return '%s-master-mixer' % self.id

state.StateBase.register_class(MasterTrackGroup)
