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

import asyncio
import os.path
import time
from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisidev import profutil
from noisidev import unittest
from noisidev import uitest
from noisicaa import audioproc
from noisicaa.ui.track_list import track_editor_tests
from . import track_ui

MT = audioproc.MusicalTime
MD = audioproc.MusicalDuration
SMPL_PATH = os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')
assert os.path.isfile(SMPL_PATH)
NON_SMPL_PATH = os.path.join(unittest.TESTDATA_DIR, 'symbol.svg')
assert os.path.isfile(NON_SMPL_PATH)


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

    async def test_add_sample(self):
        assert len(self.track.samples) == 0

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))

            with mock.patch(
                    'PyQt5.QtWidgets.QFileDialog.getOpenFileName',
                    return_value=(SMPL_PATH, None)):
                menu = await self.openContextMenu()
                await self.triggerMenuAction(menu, 'add-sample')

                t0 = time.time()
                while len(self.track.samples) == 0:
                    if t0 > time.time() + 10:
                        raise TimeoutError
                    await asyncio.sleep(0.2, loop=self.loop)

            self.assertEqual(self.track.samples[0].time, MT(2, 4))
            self.assertEqual(self.track.samples[0].sample.path, SMPL_PATH)

            self.renderWidget()
            while not ti.sample(0).isRenderComplete():
                self.renderWidget()
                await asyncio.sleep(0.2, loop=self.loop)

    async def test_add_sample_load_error(self):
        assert len(self.track.samples) == 0

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))

            with mock.patch(
                    'PyQt5.QtWidgets.QFileDialog.getOpenFileName',
                    return_value=(NON_SMPL_PATH, None)):
                menu = await self.openContextMenu()
                await self.triggerMenuAction(menu, 'add-sample')

            # Wait for the error dialog to pop up.
            t0 = time.time()
            while True:
                if t0 > time.time() + 10:
                    raise TimeoutError
                error_dialog = ti.findChild(QtWidgets.QMessageBox, 'sample-load-error')
                if error_dialog is not None:
                    error_dialog.accept()
                    break
                await asyncio.sleep(0.2, loop=self.loop)

    async def test_move_sample(self):
        ls = await self.track.load_sample(SMPL_PATH, self.loop)
        with self.project.apply_mutations('test'):
            self.track.create_sample(MT(0, 4), ls)

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(1, 4)), ti.height() // 2))
            await self.pressMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            await self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(self.track.samples[0].time, MT(1, 4))

    async def test_move_sample_abort(self):
        ls = await self.track.load_sample(SMPL_PATH, self.loop)
        with self.project.apply_mutations('test'):
            self.track.create_sample(MT(0, 4), ls)

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(1, 4)), ti.height() // 2))
            await self.pressMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            await self.clickMouseButton(Qt.RightButton)
            await self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(self.track.samples[0].time, MT(0, 4))

    async def test_profile_rendering(self):
        ls = await self.track.load_sample(SMPL_PATH, self.loop)
        with self.project.apply_mutations('test'):
            self.track.create_sample(MT(0, 4), ls)

        with self._trackItem() as ti:
            self.renderWidget()
            profutil.profile(self.id(), ti.sample(0).renderPendingCacheTiles)
            self.renderWidget()
            assert ti.sample(0).isRenderComplete()

