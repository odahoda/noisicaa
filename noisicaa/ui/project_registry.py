#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from PyQt5 import QtCore

from noisicaa import core
from noisicaa import music
from . import model

logger = logging.getLogger(__name__)


class ProjectClient(music.ProjectClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listeners = core.CallbackRegistry()

    def handle_project_mutations(self, mutations):
        self.listeners.call('project_mutations_begin')
        try:
            return super().handle_project_mutations(mutations)
        finally:
            self.listeners.call('project_mutations_end')


class Project(object):
    def __init__(self, path, event_loop, process_manager, node_db):
        self.path = path
        self.event_loop = event_loop
        self.process_manager = process_manager
        self.node_db = node_db

        self.process_address = None
        self.client = None

    @property
    def name(self):
        return os.path.basename(self.path)

    async def create_process(self):
        self.process_address = await self.process_manager.call(
            'CREATE_PROJECT_PROCESS', self.path)
        self.client = ProjectClient(
            event_loop=self.event_loop, node_db=self.node_db)
        self.client.cls_map.update(model.cls_map)
        await self.client.setup()
        await self.client.connect(self.process_address)

    async def open(self):
        await self.create_process()
        await self.client.open(self.path)

    async def create(self):
        await self.create_process()
        await self.client.create(self.path)

    async def close(self):
        await self.client.close()
        await self.client.disconnect(shutdown=True)
        await self.client.cleanup()
        self.client = None


class ProjectRegistry(QtCore.QObject):
    projectListChanged = QtCore.pyqtSignal()

    def __init__(self, event_loop, process_manager, node_db):
        super().__init__()

        self.event_loop = event_loop
        self.process_manager = process_manager
        self.node_db = node_db
        self.projects = {}

    async def open_project(self, path):
        project = Project(
            path, self.event_loop, self.process_manager, self.node_db)
        await project.open()
        self.projects[path] = project
        self.projectListChanged.emit()
        return project

    async def create_project(self, path):
        project = Project(
            path, self.event_loop, self.process_manager, self.node_db)
        await project.create()
        self.projects[path] = project
        self.projectListChanged.emit()
        return project

    async def close_project(self, project):
        await project.close()
        del self.projects[project.path]
        self.projectListChanged.emit()

    async def close_all(self):
        for project in list(self.projects.values()):
            await self.close_project(project)
        self.projectListChanged.emit()
