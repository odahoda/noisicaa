#!/usr/bin/python3

import asyncio
import logging

from noisicaa import core
from noisicaa.core import ipc

from . import mutations

logger = logging.getLogger(__name__)


class ObjectProxy(object):
    def __init__(self, obj_id, cls, address):
        self.id = obj_id
        self.cls = cls
        self.address = address


class ProjectClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None
        self._project_ready = asyncio.Event()
        self._object_map = {}
        self.project = None

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PROJECT_MUTATION', self.handle_project_mutation)
        self.server.add_command_handler(
            'PROJECT_READY', self.handle_project_ready)

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id = await self._stub.call(
            'START_SESSION', self.server.address)

    async def disconnect(self):
        if self._session_id is not None:
            await self._stub.call('END_SESSION', self._session_id)
            self._session_id = None

        if self._stub is not None:
            await self._stub.close()
            self._stub = None

    def handle_project_mutation(self, mutation):
        logger.info("Mutation received: %s" % mutation)
        try:
            if isinstance(mutation, mutations.SetProperties):
                obj = self._object_map[mutation.id]
                for prop_name, prop_type, value in mutation.properties:
                    if prop_type == 'scalar':
                        setattr(obj, prop_name, value)
                    elif prop_type == 'obj':
                        setattr(obj, prop_name, self._object_map[value] if value is not None else None)
                    elif prop_type == 'objlist':
                        l = [self._object_map[v] for v in value]
                        setattr(obj, prop_name, l)
                    else:
                        raise ValueError(
                            "Property type %s not supported." % prop_type)

            elif isinstance(mutation, mutations.AddObject):
                obj = ObjectProxy(
                    mutation.id, mutation.cls, mutation.address)
                for prop_name, prop_type, value in mutation.properties:
                    if prop_type == 'scalar':
                        setattr(obj, prop_name, value)
                    elif prop_type == 'obj':
                        setattr(obj, prop_name, self._object_map[value] if value is not None else None)
                    elif prop_type == 'objlist':
                        l = [self._object_map[v] for v in value]
                        setattr(obj, prop_name, l)
                    else:
                        raise ValueError(
                            "Property type %s not supported." % prop_type)
                self._object_map[mutation.id] = obj

            elif isinstance(mutation, mutations.UpdateObjectList):
                obj = self._object_map[mutation.id]
                lst = getattr(obj, mutation.prop_name)
                if mutation.args[0] == 'insert':
                    idx, child_id = mutation.args[1:]
                    child = self._object_map[child_id]
                    lst.insert(idx, child)
                else:
                    raise ValueError(mutation.args[0])
            else:
                raise ValueError("Unknown mutation %s received." % mutation)
        except Exception as exc:
            logger.exception("Handling of mutation %s failed:", mutation)

    def handle_project_ready(self):
        logger.info("Project ready received.")
        self._project_ready.set()

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def test(self):
        await self._stub.call('TEST')

    async def create(self, path):
        assert self.project is None
        self._project_ready.clear()
        root_id = await self._stub.call('CREATE', path)
        await self._project_ready.wait()
        self.project = self._object_map[root_id]

    async def create_inmemory(self):
        assert self.project is None
        self._project_ready.clear()
        root_id = await self._stub.call('CREATE_INMEMORY')
        await self._project_ready.wait()
        self.project = self._object_map[root_id]

    async def open(self, path):
        assert self.project is None
        self._project_ready.clear()
        root_id = await self._stub.call('OPEN', path)
        await self._project_ready.wait()
        self.project = self._object_map[root_id]

    async def close(self):
        assert self.project is not None
        await self._stub.call('CLOSE')
        self.project = None
        self._object_map.clear()

    async def send_command(self, target, command, **kwargs):
        assert self.project is not None
        result = await self._stub.call('COMMAND', target, command, kwargs)
        logger.info("Command %s completed with result=%r", command, result)
        return result
