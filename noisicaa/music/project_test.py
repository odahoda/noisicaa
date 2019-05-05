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

import builtins
from typing import cast

from mox3 import stubout
from pyfakefs import fake_filesystem

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.core import fileutil
from noisicaa.core import storage
from noisicaa import editor_main_pb2
from noisicaa import model_base
from noisicaa.builtin_nodes.score_track import model as score_track
from . import project
from . import writer_client


class PoolMixin(object):
    def setup_testcase(self):
        self.pool = project.Pool()


class BaseProjectTest(
        PoolMixin,
        unittest_mixins.NodeDBMixin,
        unittest.AsyncTestCase):
    def test_serialize(self):
        p = self.pool.create(project.BaseProject, node_db=self.node_db)
        serialized = p.serialize()
        self.assertIsInstance(serialized, model_base.ObjectTree)
        self.assertGreater(len(serialized.objects), 0)
        self.assertEqual(serialized.root, p.id)

    def test_deserialize(self):
        p = self.pool.create(project.BaseProject, node_db=self.node_db)
        p.nodes.append(self.pool.create(score_track.ScoreTrack, name='Track 1'))
        num_nodes = len(p.nodes)
        serialized = p.serialize()

        pool2 = project.Pool()
        p2 = cast(project.BaseProject, pool2.deserialize_tree(serialized))
        self.assertEqual(len(p2.nodes), num_nodes)


class ProjectTest(
        PoolMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.writer_address = None
        self.writer_client = None

    async def setup_testcase(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

        self.setup_writer_process(inline=True)

        create_process_response = editor_main_pb2.CreateProcessResponse()
        await self.process_manager_client.call(
            'CREATE_WRITER_PROCESS',
            None, create_process_response)
        self.writer_address = create_process_response.address

        self.writer_client = writer_client.WriterClient(event_loop=self.loop)
        await self.writer_client.setup()
        await self.writer_client.connect(self.writer_address)

    async def cleanup_testcase(self):
        if self.writer_client is not None:
            await self.writer_client.disconnect()
            await self.writer_client.cleanup()

        if self.writer_address is not None:
            await self.process_manager_client.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.writer_address))

    async def test_create(self):
        p = await project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            writer=self.writer_client,
            node_db=self.node_db)
        await p.close()

        self.assertTrue(self.fake_os.path.isfile('/foo.noise'))
        self.assertTrue(self.fake_os.path.isdir('/foo.data'))

        f = fileutil.File('/foo.noise')
        file_info, contents = f.read_json()
        self.assertEqual(file_info.version, 1)
        self.assertEqual(file_info.filetype, 'project-header')
        self.assertIsInstance(contents, dict)

    async def test_open_and_replay(self):
        p = await project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            writer=self.writer_client,
            node_db=self.node_db)
        try:
            with p.apply_mutations('test'):
                p.create_node('builtin://score-track')
            num_nodes = len(p.nodes)
            track_id = p.nodes[-1].id
        finally:
            await p.close()

        pool = project.Pool(project_cls=project.Project)
        p = await project.Project.open(
            path='/foo.noise',
            pool=pool,
            writer=self.writer_client,
            node_db=self.node_db)
        try:
            self.assertEqual(len(p.nodes), num_nodes)
            self.assertEqual(p.nodes[-1].id, track_id)
        finally:
            await p.close()

    async def test_create_checkpoint(self):
        p = await project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            writer=self.writer_client,
            node_db=self.node_db)
        try:
            p.create_checkpoint()
        finally:
            await p.close()

        self.assertTrue(
            self.fake_os.path.isfile('/foo.data/checkpoint.000001'))

    async def test_merge_mutations(self):
        p = await project.Project.create_blank(
            path='/foo.noise',
            pool=self.pool,
            writer=self.writer_client,
            node_db=self.node_db)
        try:
            old_bpm = p.bpm

            for i in range(old_bpm + 1, old_bpm + 10):
                with p.apply_mutations('test'):
                    p.bpm = i

            p.undo(*(await p.fetch_undo()))
            self.assertEqual(p.bpm, old_bpm)

            p.redo(*(await p.fetch_redo()))
            self.assertEqual(p.bpm, old_bpm + 9)

        finally:
            await p.close()


class ProjectPropertiesTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):
    async def test_set_bpm(self):
        with self.project.apply_mutations('test'):
            self.project.bpm = self.project.bpm + 1
