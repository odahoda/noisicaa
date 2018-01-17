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

import builtins
import json

import asynctest
from mox3 import stubout
from pyfakefs import fake_filesystem

from noisicaa.node_db.private import db as node_db
from noisicaa.core import fileutil
from noisicaa.core import storage
from . import project
from . import score_track
from . import track_group


def store_retrieve(obj):
    serialized = json.dumps(obj, cls=project.JSONEncoder)
    deserialized = json.loads(serialized, cls=project.JSONDecoder)
    return deserialized


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]


class BaseProjectTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

    async def tearDown(self):
        await self.node_db.cleanup()

    def test_serialize(self):
        p = project.BaseProject(node_db=self.node_db)
        self.assertIsInstance(p.serialize(), dict)

    def test_deserialize(self):
        p = project.BaseProject(node_db=self.node_db)
        p.master_group.tracks.append(track_group.TrackGroup(name='Sub Group'))
        state = store_retrieve(p.serialize())
        p2 = project.Project(state=state)
        self.assertEqual(len(p2.master_group.tracks), 1)

    def test_demo(self):
        p = project.BaseProject.make_demo(node_db=self.node_db)
        #pprint.pprint(p.serialize())


class ProjectTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    async def tearDown(self):
        await self.node_db.cleanup()

    def test_create(self):
        p = project.Project()
        p.create('/foo.noise')
        p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.noise'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f = fileutil.File('/foo.noise')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    def test_open_and_replay(self):
        p = project.Project(node_db=self.node_db)
        p.create('/foo.noise')
        try:
            p.dispatch_command(p.id, project.AddTrack(
                track_type='score',
                parent_group_id=p.master_group.id))
            track_id = p.master_group.tracks[-1].id
        finally:
            p.close()

        p = project.Project(node_db=self.node_db)
        p.open('/foo.noise')
        try:
            self.assertEqual(p.master_group.tracks[-1].id, track_id)
        finally:
            p.close()

    def test_create_checkpoint(self):
        p = project.Project()
        p.create('/foo.emp')
        try:
            p.create_checkpoint()
        finally:
            p.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000001'))


class CommandTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = project.BaseProject(node_db=self.node_db)

    async def tearDown(self):
        await self.node_db.cleanup()


class AddTrackTest(CommandTest):
    def test_ok(self):
        cmd = project.AddTrack(
            track_type='score',
            parent_group_id=self.project.master_group.id)
        self.project.dispatch_command(self.project.id, cmd)
        self.assertEqual(len(self.project.master_group.tracks), 1)


    def test_nested_group(self):
        cmd = project.AddTrack(
            track_type='group',
            parent_group_id=self.project.master_group.id)
        self.project.dispatch_command(self.project.id, cmd)

        self.assertIsInstance(
            self.project.master_group.tracks[0], track_group.TrackGroup)

        cmd = project.AddTrack(
            track_type='score',
            parent_group_id=self.project.master_group.tracks[0].id)
        self.project.dispatch_command(self.project.id, cmd)

        self.assertEqual(len(self.project.master_group.tracks), 1)
        self.assertEqual(len(self.project.master_group.tracks[0].tracks), 1)


class DeleteTrackTest(CommandTest):
    def test_ok(self):
        self.project.add_track(
            self.project.master_group, 0,
            score_track.ScoreTrack(name='Test'))

        cmd = project.RemoveTrack(
            track_id=self.project.master_group.tracks[0].id)
        self.project.dispatch_command(self.project.id, cmd)
        self.assertEqual(len(self.project.master_group.tracks), 0)

    def test_track_with_instrument(self):
        self.project.add_track(
            self.project.master_group, 0,
            score_track.ScoreTrack(name='Test'))
        self.project.master_group.tracks[0].instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0'

        cmd = project.RemoveTrack(
            track_id=self.project.master_group.tracks[0].id)
        self.project.dispatch_command(self.project.id, cmd)
        self.assertEqual(len(self.project.master_group.tracks), 0)

    def test_delete_nested_track(self):
        grp = track_group.TrackGroup(name='TestGroup')
        self.project.add_track(self.project.master_group, 0, grp)

        track = score_track.ScoreTrack(name='Test')
        self.project.add_track(grp, 0, track)

        cmd = project.RemoveTrack(track_id=track.id)
        self.project.dispatch_command(self.project.id, cmd)
        self.assertEqual(len(grp.tracks), 0)
