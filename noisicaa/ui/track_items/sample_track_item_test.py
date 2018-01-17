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

import unittest

from noisicaa.ui import uitest_utils
from noisicaa.ui import model
from noisicaa.ui import tools
from . import sample_track_item
from . import track_item_tests


class SampleTrackEditorItemTest(track_item_tests.TrackEditorItemTestMixin, uitest_utils.UITest):
    async def setUp(self):
        await super().setUp()

        self.project.master_group.tracks.append(model.SampleTrack(obj_id='track-1'))

        self.tool_box = sample_track_item.SampleTrackToolBox(**self.context_args)

    def _createTrackItem(self, **kwargs):
        return sample_track_item.SampleTrackEditorItem(
            track=self.project.master_group.tracks[0],
            player_state=self.player_state,
            editor=self.editor,
            **self.context_args,
            **kwargs)
