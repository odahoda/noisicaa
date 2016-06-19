#!/usr/bin/python3

import asyncio
import logging

from noisicaa import core
from noisicaa.core import ipc

from . import mutations

logger = logging.getLogger(__name__)


class ObjectProxy(object):
    def __init__(self, obj_id):
        self.id = obj_id


class ProjectClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None
        self._session_ready = asyncio.Event()
        self._object_map = {}
        self.project = None

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PROJECT_MUTATION', self.handle_project_mutation)
        self.server.add_command_handler(
            'SESSION_READY', self.handle_session_ready)

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id, root_id = await self._stub.call(
            'START_SESSION', self.server.address)
        self.project = ObjectProxy(root_id)
        self._object_map[root_id] = self.project
        await self._session_ready.wait()

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
                obj = ObjectProxy(mutation.id)
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

            else:
                raise ValueError("Unknown mutation %s received." % mutation)
        except Exception as exc:
            logger.exception("Handling of mutation %s failed:", mutation)

    def handle_session_ready(self):
        logger.info("Session ready received.")
        self._session_ready.set()

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def test(self):
        await self._stub.call('TEST')
