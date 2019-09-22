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
import shutil

from PySide2.QtCore import Qt
from mox3 import stubout
from pyfakefs import fake_filesystem

from noisidev import uitest
from noisicaa.core import fileutil
from noisicaa.core import storage
from . import project_registry


class ProjectRegistryTest(uitest.UITestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__registry = None

    async def setup_testcase(self):
        self.stubs = stubout.StubOutForTesting()
        self.addCleanup(self.stubs.SmartUnsetAll)

        # Setup fake filesystem.
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs.SmartSet(storage, 'os', self.fake_os)
        self.stubs.SmartSet(fileutil, 'os', self.fake_os)
        self.stubs.SmartSet(project_registry, 'os', self.fake_os)
        self.stubs.SmartSet(shutil, 'os', self.fake_os)
        self.stubs.SmartSet(builtins, 'open', self.fake_open)

        self.music_dir = self.fake_os.path.expanduser('~/Music/Noisicaä')
        self.fake_os.makedirs(self.music_dir)

        storage.ProjectStorage.create(self.fake_os.path.join(self.music_dir, 'proj1')).close()
        storage.ProjectStorage.create(self.fake_os.path.join(self.music_dir, 'proj2')).close()
        storage.ProjectStorage.create(self.fake_os.path.join(self.music_dir, 'proj3')).close()

        self.__registry = project_registry.ProjectRegistry(context=self.context)
        await self.__registry.setup()

    async def cleanup_testcase(self):
        if self.__registry is not None:
            await self.__registry.cleanup()

    async def test_QAbstractItemModel(self):
        self.assertEqual(self.__registry.columnCount(), 1)
        self.assertEqual(self.__registry.rowCount(), 3)

        for row, name in enumerate(['proj1', 'proj2', 'proj3']):
            self.assertEqual(
                self.__registry.data(
                    self.__registry.index(row), project_registry.Project.NameRole),
                name)
            self.assertEqual(
                self.__registry.data(
                    self.__registry.index(row), project_registry.Project.PathRole),
                self.fake_os.path.join(self.music_dir, name))
            self.assertEqual(
                self.__registry.data(
                    self.__registry.index(row), project_registry.Project.MTimeRole),
                self.fake_os.path.getmtime(
                    self.fake_os.path.join(self.music_dir, name, 'project.noise')))
            self.assertEqual(
                self.__registry.flags(self.__registry.index(row)),
                Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        self.assertEqual(len(self.__registry.projects()), 3)

    async def test_projects(self):
        self.assertEqual(len(self.__registry.projects()), 3)
        for idx, name in enumerate(['proj1', 'proj2', 'proj3']):
            proj = self.__registry.projects()[idx]
            self.assertIsInstance(proj, project_registry.Project)
            self.assertEqual(
                proj.name,
                name)
            self.assertEqual(
                proj.path,
                self.fake_os.path.join(self.music_dir, name))
            self.assertEqual(
                proj.mtime,
                self.fake_os.path.getmtime(
                    self.fake_os.path.join(self.music_dir, name, 'project.noise')))

    async def test_getProjects(self):
        self.assertIs(
            self.__registry.getProject(self.fake_os.path.join(self.music_dir, 'proj2')),
            self.__registry.projects()[1])
        with self.assertRaises(KeyError):
            self.__registry.getProject(self.fake_os.path.join(self.music_dir, 'does-not-exist'))

    async def test_project_added(self):
        storage.ProjectStorage.create(self.fake_os.path.join(self.music_dir, 'proj1b')).close()
        await self.__registry.refresh()

        self.assertEqual(len(self.__registry.projects()), 4)
        proj = self.__registry.projects()[1]
        self.assertIsInstance(proj, project_registry.Project)
        self.assertEqual(proj.name, 'proj1b')
        self.assertEqual(proj.path, self.fake_os.path.join(self.music_dir, 'proj1b'))

    async def test_project_removed(self):
        await self.__registry.projects()[1].delete()
        await self.__registry.refresh()

        self.assertEqual(len(self.__registry.projects()), 2)
        proj = self.__registry.projects()[1]
        self.assertEqual(proj.name, 'proj3')
