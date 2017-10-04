#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import base_track
from . import misc

logger = logging.getLogger(__name__)


class TrackGroup(model.TrackGroup, base_track.Track):
    def __init__(self, state=None, num_measures=None, **kwargs):
        super().__init__(state=state, **kwargs)

    @property
    def default_mixer_name(self):
        return "Group Mixer"

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
        return "Master Mixer"

    @property
    def mixer_name(self):
        return '%s-master-mixer' % self.id

state.StateBase.register_class(MasterTrackGroup)
