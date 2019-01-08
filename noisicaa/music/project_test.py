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
from typing import cast

from mox3 import stubout
from pyfakefs import fake_filesystem

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.core import fileutil
from noisicaa.core import storage
from noisicaa import model
from noisicaa.builtin_nodes.score_track import server_impl as score_track
from . import project
from . import commands_pb2
from . import commands_test


class PoolMixin(object):
    def setup_testcase(self):
        self.pool = project.Pool()


class BaseProjectTest(PoolMixin, unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    def test_serialize(self):
        p = self.pool.create(project.BaseProject, node_db=self.node_db)
        serialized = p.serialize()
        self.assertIsInstance(serialized, model.ObjectTree)
        self.assertGreater(len(serialized.objects), 0)
        self.assertEqual(serialized.root, p.id)

    def test_deserialize(self):
        p = self.pool.create(project.BaseProject, node_db=self.node_db)
        p.pipeline_graph_nodes.append(self.pool.create(score_track.ScoreTrack, name='Track 1'))
        num_nodes = len(p.pipeline_graph_nodes)
        serialized = p.serialize()

        pool2 = project.Pool()
        p2 = cast(project.BaseProject, pool2.deserialize_tree(serialized))
        self.assertEqual(len(p2.pipeline_graph_nodes), num_nodes)


class ProjectTest(PoolMixin, unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    def setup_testcase(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

    def test_create(self):
        p = project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            node_db=self.node_db)
        p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.noise'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f = fileutil.File('/foo.noise')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    def test_open_and_replay(self):
        p = project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            node_db=self.node_db)
        try:
            p.dispatch_command_proto(commands_pb2.Command(
                target=p.id,
                command='add_pipeline_graph_node',
                add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                    uri='builtin://score-track')))
            num_nodes = len(p.pipeline_graph_nodes)
            track_id = p.pipeline_graph_nodes[-1].id
        finally:
            p.close()

        pool = project.Pool(project_cls=project.Project)
        p = project.Project.open(
            path='/foo.noise',
            pool=pool,
            node_db=self.node_db)
        try:
            self.assertEqual(len(p.pipeline_graph_nodes), num_nodes)
            self.assertEqual(p.pipeline_graph_nodes[-1].id, track_id)
        finally:
            p.close()

    def test_create_checkpoint(self):
        p = project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            node_db=self.node_db)
        try:
            p.create_checkpoint()
        finally:
            p.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000001'))


class ProjectPropertiesTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):
    async def test_bpm(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='update_project_properties',
            update_project_properties=commands_pb2.UpdateProjectProperties(
                bpm=97)))
        self.assertEqual(self.project.bpm, 97)
