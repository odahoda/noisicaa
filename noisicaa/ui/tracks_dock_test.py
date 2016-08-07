#!/usr/bin/python3

import unittest
from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa import music
from . import uitest_utils
from . import tool_dock
from . import model
from . import tracks_dock


class TestTracksModel(uitest_utils.TestMixin, tracks_dock.TracksModelImpl):
    pass


class TracksModelTest(uitest_utils.UITest):
    async def setUp(self):
        await super().setUp()

        self.sheet = model.Sheet('sheet')
        self.sheet.property_track = model.SheetPropertyTrack('props')
        self.sheet.master_group = model.MasterTrackGroup('master')
        self.sheet.master_group.name = 'master'
        self.project.sheets.append(self.sheet)

    async def test_start_empty(self):
        tracks_model = TestTracksModel(**self.context, sheet=self.sheet)
        try:
            root_index = QtCore.QModelIndex()
            self.assertEqual(tracks_model.rowCount(root_index), 1)
            self.assertEqual(
                tracks_model.parent(root_index), QtCore.QModelIndex())

            master_index = tracks_model.index(0)
            self.assertEqual(
                tracks_model.data(master_index, Qt.DisplayRole), 'master')
            self.assertEqual(tracks_model.rowCount(master_index), 0)
            self.assertEqual(
                tracks_model.parent(master_index), QtCore.QModelIndex())

            track1 = model.ScoreTrack('track1')
            track1.name = 'track1'
            self.sheet.master_group.tracks.append(track1)
            self.assertEqual(tracks_model.rowCount(master_index), 1)

            track1_index = tracks_model.index(0, parent=master_index)
            self.assertEqual(
                tracks_model.data(track1_index, Qt.DisplayRole), 'track1')
            self.assertEqual(tracks_model.rowCount(track1_index), 0)
            self.assertEqual(
                tracks_model.parent(track1_index), master_index)

            grp1 = model.TrackGroup('grp1')
            grp1.name = 'grp1'
            self.sheet.master_group.tracks.append(grp1)
            self.assertEqual(tracks_model.rowCount(master_index), 2)

            grp1_index = tracks_model.index(1, parent=master_index)
            self.assertEqual(
                tracks_model.data(grp1_index, Qt.DisplayRole), 'grp1')
            self.assertEqual(tracks_model.rowCount(grp1_index), 0)
            self.assertEqual(
                tracks_model.parent(grp1_index), master_index)

            track2 = model.ScoreTrack('track2')
            track2.name = 'track2'
            grp1.tracks.append(track2)
            self.assertEqual(tracks_model.rowCount(master_index), 2)
            self.assertEqual(tracks_model.rowCount(grp1_index), 1)

            track2_index = tracks_model.index(0, parent=grp1_index)
            self.assertEqual(
                tracks_model.data(track2_index, Qt.DisplayRole), 'track2')
            self.assertEqual(tracks_model.rowCount(track2_index), 0)
            self.assertEqual(
                tracks_model.parent(track2_index), grp1_index)

            track3 = model.ScoreTrack('track3')
            track3.name = 'track3'
            grp1.tracks.append(track3)
            self.assertEqual(tracks_model.rowCount(master_index), 2)
            self.assertEqual(tracks_model.rowCount(grp1_index), 2)

            track3_index = tracks_model.index(1, parent=grp1_index)
            self.assertEqual(
                tracks_model.data(track3_index, Qt.DisplayRole), 'track3')
            self.assertEqual(tracks_model.rowCount(track3_index), 0)
            self.assertEqual(
                tracks_model.parent(track3_index), grp1_index)

        finally:
            tracks_model.close()

    async def test_start_filled(self):
        track1 = model.ScoreTrack('track1')
        track1.name = 'track1'
        self.sheet.master_group.tracks.append(track1)
        grp1 = model.TrackGroup('grp1')
        grp1.name = 'grp1'
        self.sheet.master_group.tracks.append(grp1)
        track2 = model.ScoreTrack('track2')
        track2.name = 'track2'
        grp1.tracks.append(track2)
        track3 = model.ScoreTrack('track3')
        track3.name = 'track3'
        grp1.tracks.append(track3)

        tracks_model = TestTracksModel(**self.context, sheet=self.sheet)
        try:
            root_index = QtCore.QModelIndex()
            self.assertEqual(tracks_model.rowCount(root_index), 1)
            self.assertEqual(
                tracks_model.parent(root_index), QtCore.QModelIndex())

            master_index = tracks_model.index(0)
            self.assertEqual(
                tracks_model.data(master_index, Qt.DisplayRole), 'master')
            self.assertEqual(tracks_model.rowCount(master_index), 2)
            self.assertEqual(
                tracks_model.parent(master_index), QtCore.QModelIndex())

            track1_index = tracks_model.index(0, parent=master_index)
            self.assertEqual(
                tracks_model.data(track1_index, Qt.DisplayRole), 'track1')
            self.assertEqual(tracks_model.rowCount(track1_index), 0)
            self.assertEqual(
                tracks_model.parent(track1_index), master_index)

            grp1_index = tracks_model.index(1, parent=master_index)
            self.assertEqual(
                tracks_model.data(grp1_index, Qt.DisplayRole), 'grp1')
            self.assertEqual(tracks_model.rowCount(grp1_index), 2)
            self.assertEqual(
                tracks_model.parent(grp1_index), master_index)

            track2_index = tracks_model.index(0, parent=grp1_index)
            self.assertEqual(
                tracks_model.data(track2_index, Qt.DisplayRole), 'track2')
            self.assertEqual(tracks_model.rowCount(track2_index), 0)
            self.assertEqual(
                tracks_model.parent(track2_index), grp1_index)

            track3_index = tracks_model.index(1, parent=grp1_index)
            self.assertEqual(
                tracks_model.data(track3_index, Qt.DisplayRole), 'track3')
            self.assertEqual(tracks_model.rowCount(track3_index), 0)
            self.assertEqual(
                tracks_model.parent(track3_index), grp1_index)
        finally:
            tracks_model.close()

    async def test_delete_track(self):
        track1 = model.ScoreTrack('track1')
        track1.name = 'track1'
        self.sheet.master_group.tracks.append(track1)
        grp1 = model.TrackGroup('grp1')
        grp1.name = 'grp1'
        self.sheet.master_group.tracks.append(grp1)
        track2 = model.ScoreTrack('track2')
        track2.name = 'track2'
        grp1.tracks.append(track2)
        track3 = model.ScoreTrack('track3')
        track3.name = 'track3'
        grp1.tracks.append(track3)

        tracks_model = TestTracksModel(**self.context, sheet=self.sheet)
        try:
            master_index = tracks_model.index(0)
            grp1_index = tracks_model.index(1, parent=master_index)
            self.assertEqual(tracks_model.rowCount(grp1_index), 2)

            del grp1.tracks[0]
            self.assertEqual(tracks_model.rowCount(grp1_index), 1)

            track3_index = tracks_model.index(0, parent=grp1_index)
            self.assertEqual(
                tracks_model.data(track3_index, Qt.DisplayRole), 'track3')

        finally:
            tracks_model.close()

    async def test_track_property_changed(self):
        track1 = model.ScoreTrack('track1')
        track1.name = 'track1'
        self.sheet.master_group.tracks.append(track1)
        grp1 = model.TrackGroup('grp1')
        grp1.name = 'grp1'
        self.sheet.master_group.tracks.append(grp1)
        track2 = model.ScoreTrack('track2')
        track2.name = 'track2'
        grp1.tracks.append(track2)
        track3 = model.ScoreTrack('track3')
        track3.name = 'track3'
        grp1.tracks.append(track3)

        tracks_model = TestTracksModel(**self.context, sheet=self.sheet)
        try:
            master_index = tracks_model.index(0)
            grp1_index = tracks_model.index(1, parent=master_index)
            track3_index = tracks_model.index(1, parent=grp1_index)

            listener = mock.Mock()
            tracks_model.dataChanged.connect(listener)

            track3.name = 'changed'
            self.assertEqual(listener.call_count, 1)
            (first, last, roles), _ = listener.call_args
            self.assertEqual(first, track3_index)
            self.assertEqual(last, track3_index)
            self.assertEqual(roles, [])
            self.assertEqual(
                tracks_model.data(track3_index, Qt.DisplayRole), 'changed')

            listener.reset_mock()
            track3.visible = False
            self.assertEqual(listener.call_count, 1)
            (first, last, roles), _ = listener.call_args
            self.assertEqual(first, track3_index)
            self.assertEqual(last, track3_index)
            self.assertEqual(roles, [])
            self.assertFalse(
                tracks_model.data(
                    track3_index, TestTracksModel.VisibleRole))

            listener.reset_mock()
            track3.muted = True
            self.assertEqual(listener.call_count, 1)
            (first, last, roles), _ = listener.call_args
            self.assertEqual(first, track3_index)
            self.assertEqual(last, track3_index)
            self.assertEqual(roles, [])
            self.assertTrue(
                tracks_model.data(
                    track3_index, TestTracksModel.MuteRole))

        finally:
            tracks_model.close()


if __name__ == '__main__':
    unittest.main()
