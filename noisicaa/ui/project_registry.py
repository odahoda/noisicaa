#!/usr/bin/python3

import logging

from noisicaa import music

logger = logging.getLogger(__name__)


class Project(object):
    def __init__(self, path, event_loop, process_manager):
        self.path = path
        self.event_loop = event_loop
        self.process_manager = process_manager

        self.process_address = None
        self.client = None

    async def create_process(self):
        self.process_address = await self.process_manager.call(
            'CREATE_PROJECT_PROCESS', self.path)
        self.client = music.ProjectClient(self.event_loop)
        await self.client.setup()
        await self.client.connect(self.process_address)

    async def open(self):
        await self.create_process()
        await self.client.open(self.path)

    async def create(self):
        await self.create_process()
        await self.client.create(self.path)


class ProjectRegistry(object):
    def __init__(self, event_loop, process_manager):
        self.event_loop = event_loop
        self.process_manager = process_manager
        self.projects = {}

    async def open_project(self, path):
        project = Project(path, self.event_loop, self.process_manager)
        await project.open()
        self.projects[path] = project
        return project

    async def create_project(self, path):
        project = Project(path, self.event_loop, self.process_manager)
        await project.create()
        self.projects[path] = project
        return project
