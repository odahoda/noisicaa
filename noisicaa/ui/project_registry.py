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
import logging
import os.path
from typing import Dict

from PyQt5 import QtCore

from noisicaa import lv2
from noisicaa import music
from noisicaa.core import ipc
from noisicaa import node_db as node_db_lib

logger = logging.getLogger(__name__)


class Project(object):
    def __init__(
            self,
            path: str,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            process_manager: ipc.Stub,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
            tmp_dir: str
    ) -> None:
        self.path = path
        self.event_loop = event_loop
        self.server = server
        self.process_manager = process_manager
        self.node_db = node_db
        self.urid_mapper = urid_mapper
        self.tmp_dir = tmp_dir

        self.client = None  # type: music.ProjectClient

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    async def create_process(self) -> None:
        self.client = music.ProjectClient(
            event_loop=self.event_loop,
            server=self.server,
            node_db=self.node_db,
            urid_mapper=self.urid_mapper,
            manager=self.process_manager,
            tmp_dir=self.tmp_dir,
        )
        await self.client.setup()

    async def open(self) -> None:
        await self.create_process()
        await self.client.open(self.path)

    async def create(self) -> None:
        await self.create_process()
        await self.client.create(self.path)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            await self.client.cleanup()
            self.client = None


class ProjectRegistry(QtCore.QObject):
    projectListChanged = QtCore.pyqtSignal()

    def __init__(
            self,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            process_manager: ipc.Stub,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
            tmp_dir: str) -> None:
        super().__init__()

        self.event_loop = event_loop
        self.server = server
        self.process_manager = process_manager
        self.node_db = node_db
        self.urid_mapper = urid_mapper
        self.tmp_dir = tmp_dir
        self.projects = {}  # type: Dict[str, Project]

    def add_project(self, path: str) -> Project:
        project = Project(
            path,
            self.event_loop,
            self.server,
            self.process_manager,
            self.node_db,
            self.urid_mapper,
            self.tmp_dir)
        self.projects[path] = project
        self.projectListChanged.emit()
        return project

    async def close_project(self, project: Project) -> None:
        await project.close()
        del self.projects[project.path]
        self.projectListChanged.emit()

    async def close_all(self) -> None:
        for project in list(self.projects.values()):
            await self.close_project(project)
        self.projectListChanged.emit()
