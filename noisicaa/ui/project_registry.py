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

import logging
import os.path
from typing import Any, Dict, List, Iterable

from PyQt5 import QtCore

from noisicaa import music
from . import ui_base

logger = logging.getLogger(__name__)


class Project(ui_base.CommonMixin, object):
    def __init__(self, *, path: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.path = path
        self.client = None  # type: music.ProjectClient

    @property
    def name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]

    async def __create_process(self) -> None:
        self.client = music.ProjectClient(
            event_loop=self.event_loop,
            server=self.app.process.server,
            node_db=self.app.node_db,
            urid_mapper=self.app.urid_mapper,
            manager=self.app.process.manager,
            tmp_dir=self.app.process.tmp_dir,
        )
        await self.client.setup()

    async def open(self) -> None:
        await self.__create_process()
        await self.client.open(self.path)

    async def create(self) -> None:
        await self.__create_process()
        await self.client.create(self.path)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            await self.client.cleanup()
            self.client = None


class ProjectRegistry(ui_base.CommonMixin, QtCore.QObject):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__projects = {}  # type: Dict[str, Project]

    @property
    def projects(self) -> List[Project]:
        return list(self.__projects.values())

    async def setup(self) -> None:
        # TODO: get list of directories from settings
        directories = ['~/Music/Noisicaä', '/lala']

        projects = await self.event_loop.run_in_executor(None, self.__scan_projects, directories)
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
                    projects.append(Project(path=filepath, context=self.context))

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
