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

    def test_segments_changed(self):
        with self._trackItem():
            with self.project.apply_mutations('test'):
                seg = self.track.create_segment(MT(3, 4), MD(2, 4))

            self.processQtEvents()
            self.renderWidget()

            with self.project.apply_mutations('test'):
                self.track.remove_segment(seg)

            self.processQtEvents()
            self.renderWidget()

    def test_events_changed(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))
            seg.segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            seg.segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))

        with self._trackItem():
            with self.project.apply_mutations('test'):
                seg.segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
                seg.segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))

            self.processQtEvents()
            self.renderWidget()

            with self.project.apply_mutations('test'):
                while len(seg.segment.events) > 0:
                    seg.segment.remove_event(seg.segment.events[0])

            self.processQtEvents()
            self.renderWidget()

    def test_events_edited(self):
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
            self.processQtEvents()
            self.renderWidget()

            self.assertEqual(len(seg.segment.events), 4)

    def test_scroll(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(2, 4))

        with self._trackItem() as ti:
            yoff = ti.yOffset()
            self.scrollWheel(-1)
            self.assertGreater(ti.yOffset(), yoff)
            self.scrollWheel(1)
            self.assertEqual(ti.yOffset(), yoff)

    def test_playback_pos(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(2, 4))
            self.track.create_segment(MT(3, 4), MD(2, 4))
            self.track.create_segment(MT(5, 4), MD(2, 4))

        with self._trackItem() as ti:
            t = MT(0, 1)
            while t < MT(8, 4):
                ti.setPlaybackPos(t)
                self.processQtEvents()
                t += MD(1, 32)

    def test_change_row_height(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = self.openContextMenu()
            incr_button = menu.findChild(QtWidgets.QAbstractButton, 'incr-row-height')
            assert incr_button is not None
            decr_button = menu.findChild(QtWidgets.QAbstractButton, 'decr-row-height')
            assert decr_button is not None

            h = ti.gridYSize()
            incr_button.click()
            self.assertGreater(ti.gridYSize(), h)
            decr_button.click()
            self.assertEqual(ti.gridYSize(), h)

    def test_move_segment(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(1, 4)), ti.height() // 2))
            self.pressMouseButton(Qt.LeftButton)
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(3, 4)), ti.height() // 2))
            self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(2, 4))

    def test_resize_segment(self):
        with self.project.apply_mutations('test'):
            seg = self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(4, 4)), ti.height() // 2))
            self.pressMouseButton(Qt.LeftButton)
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(5, 4)), ti.height() // 2))
            self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(0, 4))
            self.assertEqual(seg.segment.duration, MD(5, 4))

            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(0, 4)), ti.height() // 2))
            self.pressMouseButton(Qt.LeftButton)
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            self.releaseMouseButton(Qt.LeftButton)

            self.assertEqual(seg.time, MT(2, 4))
            self.assertEqual(seg.segment.duration, MD(3, 4))

    def test_add_segment(self):
        assert len(self.track.segments) == 0

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = self.openContextMenu()
            action = menu.findChild(QtWidgets.QAction, 'add-segment')
            assert action is not None
            self.assertTrue(action.isEnabled())
            action.trigger()

            self.assertEqual(len(self.track.segments), 1)
            self.assertEqual(self.track.segments[0].time, MT(2, 4))

    def test_delete_segment(self):
        with self.project.apply_mutations('test'):
            self.track.create_segment(MT(0, 4), MD(4, 4))

        with self._trackItem() as ti:
            self.moveMouse(QtCore.QPoint(ti.timeToX(MT(2, 4)), ti.height() // 2))
            menu = self.openContextMenu()
            action = menu.findChild(QtWidgets.QAction, 'delete-segment')
            assert action is not None
            self.assertTrue(action.isEnabled())
            action.trigger()

            self.assertEqual(len(self.track.segments), 0)
