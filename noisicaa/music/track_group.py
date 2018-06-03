#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Any, Optional, Dict  # pylint: disable=unused-import

from noisicaa import model
from noisicaa import core  # pylint: disable=unused-import
from . import pmodel
from . import base_track

logger = logging.getLogger(__name__)


class TrackGroup(pmodel.TrackGroup, base_track.Track):
    def create(self, *, num_measures: Optional[int] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

    def create_track_connector(self, **kwargs: Any) -> base_track.TrackConnector:
        raise RuntimeError("No track connector for TrackGroup")

    @property
    def default_mixer_name(self) -> str:
        return "Group Mixer"

    def add_pipeline_nodes(self) -> None:
        super().add_pipeline_nodes()
        for track in self.tracks:
            track.add_pipeline_nodes()

    def remove_pipeline_nodes(self) -> None:
        for track in self.tracks:
            track.remove_pipeline_nodes()
        super().remove_pipeline_nodes()


class MasterTrackGroup(pmodel.MasterTrackGroup, TrackGroup):
    @property
    def parent_audio_sink_name(self) -> str:
        return 'sink'

    @property
    def parent_audio_sink_node(self) -> pmodel.BasePipelineGraphNode:
        return self.project.audio_out_node

    @property
    def relative_position_to_parent_audio_out(self) -> model.Pos2F:
        return model.Pos2F(-200, 0)

    @property
    def default_mixer_name(self) -> str:
        return "Master Mixer"

    @property
    def mixer_name(self) -> str:
        return '%016x-master-mixer' % self.id
