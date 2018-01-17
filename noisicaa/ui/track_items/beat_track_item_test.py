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
from . import beat_track_item
from . import track_item_tests


class BeatTrackEditorItemTest(track_item_tests.TrackEditorItemTestMixin, uitest_utils.UITest):
    async def setUp(self):
        await super().setUp()

        self.project.master_group.tracks.append(model.BeatTrack(obj_id='track-1'))

        m = model.PropertyMeasure(obj_id='msr-0.1')
        self.obj_map[m.id] = m
        self.project.property_track.measure_heap.append(m)
        mref = model.MeasureReference(obj_id='msr-ref-0.1')
        self.obj_map[mref.id] = mref
        mref.measure_id = m.id
        self.project.property_track.measure_list.append(mref)

        m = model.BeatMeasure(obj_id='msr-1.1')
        self.obj_map[m.id] = m
        self.project.master_group.tracks[0].measure_heap.append(m)
        mref = model.MeasureReference(obj_id='msr-ref-1.1')
        self.obj_map[mref.id] = mref
        mref.measure_id = m.id
        self.project.master_group.tracks[0].measure_list.append(mref)

        self.tool_box = beat_track_item.BeatToolBox(**self.context_args)

    def _createTrackItem(self, **kwargs):
        return beat_track_item.BeatTrackEditorItem(
            track=self.project.master_group.tracks[0],
            player_state=self.player_state,
            editor=self.editor,
            **self.context_args,
            **kwargs)

    @unittest.skip("Segfaults")
    def test_paint(self):
        pass
