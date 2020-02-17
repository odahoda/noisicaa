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

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisidev import uitest
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.ui import pianoroll
from noisicaa.ui.track_list import track_editor_tests
from . import track_ui


MT = audioproc.MusicalTime
MD = audioproc.MusicalDuration
MEVT = value_types.MidiEvent
NOTE_ON = lambda channel, pitch, velocity: bytes([0x90 | channel, pitch, velocity])
NOTE_OFF = lambda channel, pitch: bytes([0x80 | channel, pitch, 0])


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

    async def test_segments_changed(self):
        with self._trackItem():
            with self.project.apply_mutations('test'):
                seg = self.track.create_segment(MT(3, 4), MD(2, 4))

            await self.processQtEvents()
            self.renderWidget()

            with self.project.apply_mutations('test'):
                self.track.remove_segment(seg)

            await self.processQtEvents()
            self.renderWidget()

    async def test_events_changed(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))
            seg.segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            seg.segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))

        with self._trackItem():
            with self.project.apply_mutations('test'):
                seg.segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
                seg.segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))

            await self.processQtEvents()
            self.renderWidget()

            with self.project.apply_mutations('test'):
                while len(seg.segment.events) > 0:
                    seg.segment.remove_event(seg.segment.events[0])

            await self.processQtEvents()
            self.renderWidget()

    async def test_events_edited(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))
            seg.segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            seg.segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))

        with self._trackItem() as ti:
            editor = ti.findChild(track_ui.SegmentEditor, 'segment-editor[%016x]' % seg.id)
            assert editor is not None
            grid = editor.findChild(pianoroll.PianoRollGrid, 'grid')
            assert grid is not None

            with grid.collect_mutations():
                grid.addEvent(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
                grid.addEvent(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            await self.processQtEvents()
            self.renderWidget()

            self.assertEqual(len(seg.segment.events), 4)

    async def test_scroll(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(2, 4))

        with self._trackItem() as ti:
            yoff = ti.yOffset()
            await self.scrollWheel(-1)
            self.assertGreater(ti.yOffset(), yoff)
            await self.scrollWheel(1)
            self.assertEqual(ti.yOffset(), yoff)

    async def test_playback_pos(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(2, 4))
            self.track.create_segment(MT(3, 4), MD(2, 4))
            self.track.create_segment(MT(5, 4), MD(2, 4))

        with self._trackItem() as ti:
            t = MT(0, 1)
            while t < MT(8, 4):
                ti.setPlaybackPosition(t)
                await self.processQtEvents()
                t += MD(1, 32)

    async def test_change_row_height(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = await self.openContextMenu()
            incr_button = menu.findChild(QtWidgets.QAbstractButton, 'incr-row-height')
            assert incr_button is not None
            decr_button = menu.findChild(QtWidgets.QAbstractButton, 'decr-row-height')
            assert decr_button is not None

            h = ti.gridYSize()
            incr_button.click()
            self.assertGreater(ti.gridYSize(), h)
            decr_button.click()
            self.assertEqual(ti.gridYSize(), h)

    async def test_move_segment(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(1, 4)), ti.height() // 2))
            await self.pressMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(3, 4)), ti.height() // 2))
            await self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(2, 4))

    async def test_resize_segment(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(4, 4)), ti.height() // 2))
            await self.pressMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(5, 4)), ti.height() // 2))
            await self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(0, 4))
            self.assertEqual(seg.segment.duration, MD(5, 4))

            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(0, 4)), ti.height() // 2))
            await self.pressMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            await self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(2, 4))
            self.assertEqual(seg.segment.duration, MD(3, 4))

    async def test_add_segment(self):
        assert len(self.track.segments) == 0

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = await self.openContextMenu()
            await self.triggerMenuAction(menu, 'add-segment')

            self.assertEqual(len(self.track.segments), 1)
            self.assertEqual(self.track.segments[0].time, MT(2, 4))

    async def test_delete_segment(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = await self.openContextMenu()
            await self.triggerMenuAction(menu, 'delete-segment')

            self.assertEqual(len(self.track.segments), 0)

    async def test_split_segment(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            ti.setPlaybackPosition(MT(3, 4))
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(3, 4)), ti.height() // 2))
            menu = await self.openContextMenu()
            await self.triggerMenuAction(menu, 'split-segment')

            self.assertEqual(len(self.track.segments), 2)
            self.assertEqual(self.track.segments[0].time, MT(0, 4))
            self.assertEqual(self.track.segments[0].segment.duration, MD(3, 4))
            self.assertEqual(self.track.segments[1].time, MT(3, 4))
            self.assertEqual(self.track.segments[1].segment.duration, MD(1, 4))

    async def test_select_segments(self):
        with self.project.apply_mutations('test'):
            ref1 = self.track.create_segment(MT(0, 4), MD(4, 4))
            ref2 = self.track.create_segment(MT(6, 4), MD(4, 4))
            ref3 = self.track.create_segment(MT(12, 4), MD(4, 4))
            ref4 = self.track.create_segment(MT(18, 4), MD(4, 4))

        with self._trackItem() as ti:
            selected = lambda: {segment.segmentRef().id for segment in ti.selection()}

            self.assertEqual(selected(), set())
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            await self.clickMouseButton(Qt.LeftButton)
            self.assertEqual(selected(), {ref1.id})

            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(8, 4)), ti.height() // 2))
            await self.clickMouseButton(Qt.LeftButton)
            self.assertEqual(selected(), {ref2.id})

            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(14, 4)), ti.height() // 2))
            await self.pressKey(Qt.Key_Control)
            await self.clickMouseButton(Qt.LeftButton)
            await self.releaseKey(Qt.Key_Control)
            self.assertEqual(selected(), {ref2.id, ref3.id})

            await self.pressKey(Qt.Key_Control)
            await self.clickMouseButton(Qt.LeftButton)
            await self.releaseKey(Qt.Key_Control)
            self.assertEqual(selected(), {ref2.id})

            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(11, 4)), ti.height() // 2))
            await self.clickMouseButton(Qt.LeftButton)
            self.assertEqual(selected(), set())

            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(8, 4)), ti.height() // 2))
            await self.clickMouseButton(Qt.LeftButton)
            await self.moveMouse(QtCore.QPoint(ti.timeToX(MT(20, 4)), ti.height() // 2))
            await self.pressKey(Qt.Key_Shift)
            await self.clickMouseButton(Qt.LeftButton)
            await self.releaseKey(Qt.Key_Shift)
            self.assertEqual(selected(), {ref2.id, ref3.id, ref4.id})

    async def test_select_all_segment(self):
        with self.project.apply_mutations('test'):
            ref1 = self.track.create_segment(MT(0, 4), MD(4, 4))
            ref2 = self.track.create_segment(MT(6, 4), MD(4, 4))

        with self._trackItem() as ti:
            menu = await self.openContextMenu()
            await self.triggerMenuAction(menu, 'select-all')

            self.assertEqual(
                {segment.segmentRef().id for segment in ti.selection()},
                {ref1.id, ref2.id})

    async def test_clear_selection_segment(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))
            self.track.create_segment(MT(6, 4), MD(4, 4))

        with self._trackItem() as ti:
            ti.addToSelection(ti.segments[0])

            menu = await self.openContextMenu()
            await self.triggerMenuAction(menu, 'clear-selection')

            self.assertEqual(len(ti.selection()), 0)
