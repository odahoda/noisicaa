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
from typing import Dict, List, Iterable

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
    ) -> None:
        self.path = path
        self.client = None  # type: music.ProjectClient

    @property
    def name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]

    async def __create_process(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            process_manager: ipc.Stub,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
            tmp_dir: str
    ) -> None:
        self.client = music.ProjectClient(
            event_loop=event_loop,
            server=server,
            node_db=node_db,
            urid_mapper=urid_mapper,
            manager=process_manager,
            tmp_dir=tmp_dir,
        )
        await self.client.setup()

    async def open(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            process_manager: ipc.Stub,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
            tmp_dir: str
    ) -> None:
        await self.__create_process(
            event_loop=event_loop,
            server=server,
            node_db=node_db,
            urid_mapper=urid_mapper,
            process_manager=process_manager,
            tmp_dir=tmp_dir,
        )
        await self.client.open(self.path)

    async def create(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            server: ipc.Server,
            process_manager: ipc.Stub,
            node_db: node_db_lib.NodeDBClient,
            urid_mapper: lv2.ProxyURIDMapper,
            tmp_dir: str
    ) -> None:
        await self.create_process(
            event_loop=event_loop,
            server=server,
            node_db=node_db,
            urid_mapper=urid_mapper,
            process_manager=process_manager,
            tmp_dir=tmp_dir,
        )
        await self.client.create(self.path)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            await self.client.cleanup()
            self.client = None


class ProjectRegistry(QtCore.QObject):
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()

        self.__event_loop = event_loop
        self.__projects = {}  # type: Dict[str, Project]

    @property
    def projects(self) -> List[Project]:
        return list(self.__projects.values())

    async def setup(self) -> None:
        # TODO: get list of directories from settings
        directories = ['~/Music/Noisicaä', '/lala']

        projects = await self.__event_loop.run_in_executor(None, self.__scan_projects, directories)
        self.__projects = {project.path: project for project in projects}

    async def cleanup(self) -> None:
        while self.__projects:
            _, project = self.__projects.popitem()
            await project.close()

    def __scan_projects(self, directories: Iterable[str]) -> List[Project]:
        projects = []  # type: List[Project]
        for directory in directories:
            directory = os.path.expanduser(directory)
            directory = os.path.abspath(directory)
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    if filename.endswith('.noise'):
                        data_dir_name = filename[:-6] + '.data'
                        if data_dir_name in dirnames:
                            dirnames.remove(data_dir_name)

                    filepath = os.path.join(dirpath, filename)
                    projects.append(Project(filepath))

        return projects

    # def add_project(self, path: str) -> Project:
    #     project = Project(
    #         path,
    #         self.event_loop,
    #         self.server,
    #         self.process_manager,
    #         self.node_db,
    #         self.urid_mapper,
    #         self.tmp_dir)
    #     self.projects[path] = project
    #     return project

    # async def close_project(self, project: Project) -> None:
    #     await project.close()
    #     del self.projects[project.path]

    # async def close_all(self) -> None:
    #     for project in list(self.projects.values()):
    #         await self.close_project(project)
