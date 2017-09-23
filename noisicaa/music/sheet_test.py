#!/usr/bin/python3

import asynctest
import unittest

from noisicaa.node_db.private import db as node_db
from . import project
from . import sheet
from . import score_track
from . import track_group


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]


class SheetCommandTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = project.BaseProject(node_db=self.node_db)
        self.sheet = sheet.Sheet(name='Test')
        self.project.add_sheet(self.sheet)

    async def tearDown(self):
        await self.node_db.cleanup()


class AddTrackTest(SheetCommandTest):
    def test_ok(self):
        cmd = sheet.AddTrack(
            track_type='score',
            parent_group_id=self.sheet.master_group.id)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.master_group.tracks), 1)


    def test_nested_group(self):
        cmd = sheet.AddTrack(
            track_type='group',
            parent_group_id=self.sheet.master_group.id)
        self.project.dispatch_command(self.sheet.id, cmd)

        self.assertIsInstance(
            self.sheet.master_group.tracks[0], track_group.TrackGroup)

        cmd = sheet.AddTrack(
            track_type='score',
            parent_group_id=self.sheet.master_group.tracks[0].id)
        self.project.dispatch_command(self.sheet.id, cmd)

        self.assertEqual(len(self.sheet.master_group.tracks), 1)
        self.assertEqual(len(self.sheet.master_group.tracks[0].tracks), 1)


class DeleteTrackTest(SheetCommandTest):
    def test_ok(self):
        self.sheet.add_track(
            self.sheet.master_group, 0,
            score_track.ScoreTrack(name='Test'))

        cmd = sheet.RemoveTrack(
            track_id=self.sheet.master_group.tracks[0].id)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.master_group.tracks), 0)

    def test_track_with_instrument(self):
        self.sheet.add_track(
            self.sheet.master_group, 0,
            score_track.ScoreTrack(name='Test'))
        self.sheet.master_group.tracks[0].instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0'

        cmd = sheet.RemoveTrack(
            track_id=self.sheet.master_group.tracks[0].id)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.master_group.tracks), 0)

    def test_delete_nested_track(self):
        grp = track_group.TrackGroup(name='TestGroup')
        self.sheet.add_track(self.sheet.master_group, 0, grp)

        track = score_track.ScoreTrack(name='Test')
        self.sheet.add_track(grp, 0, track)

        cmd = sheet.RemoveTrack(track_id=track.id)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(grp.tracks), 0)


if __name__ == '__main__':
    unittest.main()
