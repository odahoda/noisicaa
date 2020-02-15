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

import os.path
from unittest import mock

from PyQt5 import QtCore

from noisidev import unittest
from noisidev import uitest
from noisicaa import audioproc
from noisicaa.ui.track_list import track_editor_tests
from . import track_ui

MT = audioproc.MusicalTime
MD = audioproc.MusicalDuration


class SampleTrackEditorItemTest(track_editor_tests.TrackEditorItemTestMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.track = self.project.create_node('builtin://sample-track')

    def _createTrackItem(self, **kwargs):
        return track_ui.SampleTrackEditor(
            track=self.track,
            player_state=self.player_state,
            editor=self.editor,
            context=self.context,
            **kwargs)

    def test_add_sample(self):
        assert len(self.track.samples) == 0

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))

            SMPL_PATH = os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')

            with mock.patch(
                    'PyQt5.QtWidgets.QFileDialog.getOpenFileName',
                    return_value=(SMPL_PATH, None)):
                menu = self.openContextMenu()
                self.triggerMenuAction(menu, 'add-sample')

            self.assertEqual(len(self.track.samples), 1)
            self.assertEqual(self.track.samples[0].time, MT(2, 4))
            self.assertEqual(self.track.samples[0].sample.path, SMPL_PATH)
