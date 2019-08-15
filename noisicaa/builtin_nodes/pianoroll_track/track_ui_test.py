#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

from noisidev import uitest
from noisicaa import music
from noisicaa import audioproc
from . import track_ui
from noisicaa.ui.track_list import track_editor_tests


class PianoRollTrackEditorTest(track_editor_tests.TrackEditorItemTestMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.track = self.project.create_node('builtin://pianoroll-track')

    def _createTrackItem(self, **kwargs):
        return track_ui.PianoRollTrackEditor(
            track=self.track,
            player_state=self.player_state,
            editor=self.editor,
            context=self.context,
            **kwargs)

    def test_segments_changed(self):
        with self._trackItem() as ti:
            with self.project.apply_mutations('test'):
                ref = self.track.create_segment(
                    audioproc.MusicalTime(3, 4),
                    audioproc.MusicalDuration(2, 4))

            with self.project.apply_mutations('test'):
                self.track.remove_segment(ref)
