#!/usr/bin/python3

import asyncio
import logging

from noisicaa import core
from noisicaa.core import ipc

from . import mutations

logger = logging.getLogger(__name__)


# TODO: merge with other one
class ObjectNotAttachedError(Exception):
    pass


class ObjectList(object):
    def __init__(self, prop_name, instance):
        self._prop_name = prop_name
        self._instance = instance
        self._objs = []

    def __len__(self):
        return len(self._objs)

    def __getitem__(self, idx):
        return self._objs[idx]

    def __setitem__(self, idx, obj):
        self.__delitem__(idx)
        self.insert(idx, obj)

    def __delitem__(self, idx):
        self._objs[idx].detach()
        self._objs[idx].clear_parent_container()
        del self._objs[idx]
        for i in range(idx, len(self._objs)):
            self._objs[i].set_index(i)
        self._instance.listeners.call(self._prop_name, 'delete', idx)

    def append(self, obj):
        self.insert(len(self._objs), obj)

    def insert(self, idx, obj):
        obj.attach(self._instance)
        obj.set_parent_container(self)
        self._objs.insert(idx, obj)
        for i in range(idx, len(self._objs)):
            self._objs[i].set_index(i)
        self._instance.listeners.call(self._prop_name, 'insert', idx, obj)

    def clear(self):
        for obj in self._objs:
            obj.detach()
            obj.clear_parent_container()
        self._objs.clear()
        self._instance.listeners.call(self._prop_name, 'clear')


class ObjectProxy(object):
    def __init__(self, obj_id, cls):
        self.id = obj_id
        self.cls = cls
        self.attrs = {}
        self.parent = None
        self.is_root = False
        self.listeners = core.CallbackRegistry()
        self.__parent_container = None
        self.__index = None

    @property
    def root(self):
        if self.parent is None:
            if self.is_root:
                return self
            raise ObjectNotAttachedError
        return self.parent.root

    def attach(self, parent):
        assert self.parent is None
        self.parent = parent

    def detach(self):
        assert self.parent is not None
        self.parent = None

    def __getattr__(self, name):
        try:
            return self.attrs[name]
        except KeyError:
            raise AttributeError("%s has no property %s" % (self.cls, name)) from None

    def set_attribute(self, name, value):
        # TODO: fire off listeners
        self.attrs[name] = value

    def set_parent_container(self, prop):
        self.__parent_container = prop

    def clear_parent_container(self):
        self.__parent_container = None
        self.__index = None

    def set_index(self, index):
        if self.__parent_container is None:
            raise ObjectNotAttachedError
        self.__index = index

    @property
    def index(self):
        if self.__parent_container is None:
            raise ObjectNotAttachedError
        assert self.__index is not None
        return self.__index

    @property
    def is_first(self):
        if self.__index is None:
            raise NotListMemberError
        return self.__index == 0

    @property
    def is_last(self):
        if self.__index is None:
            raise NotListMemberError
        return self.__index == len(self.__parent_container) - 1

    @property
    def prev_sibling(self):
        if self.is_first:
            raise IndexError("First list member has no previous sibling.")
        return self.__parent_container[self.index - 1]

    @property
    def next_sibling(self):
        if self.is_last:
            raise IndexError("Last list member has no next sibling.")
        return self.__parent_container[self.index + 1]


class ProjectClientBase(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()



class ProjectClientMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub = None
        self._session_id = None
        self._object_map = {}
        self.project = None

    def __set_project(self, root_id):
        assert self.project is None
        self.project = self._object_map[root_id]
        self.project.is_root = True

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PROJECT_MUTATION', self.handle_project_mutation)
        self.server.add_command_handler(
            'PROJECT_CLOSED', self.handle_project_closed)

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id, root_id = await self._stub.call(
            'START_SESSION', self.server.address)
        if root_id is not None:
            # Connected to a loaded project.
            self.__set_project(root_id)

    async def disconnect(self):
        if self._session_id is not None:
            await self._stub.call('END_SESSION', self._session_id)
            self._session_id = None

        if self._stub is not None:
            await self._stub.close()
            self._stub = None

    def apply_properties(self, obj, properties):
        for prop_name, prop_type, value in properties:
            if prop_type == 'scalar':
                obj.set_attribute(prop_name, value)
            elif prop_type == 'list':
                obj.set_attribute(prop_name, value)
            elif prop_type == 'obj':
                # TODO: detach prev child.
                child = None
                if value is not None:
                    child = self._object_map[value]
                    child.attach(obj)
                obj.set_attribute(prop_name, child)
            elif prop_type == 'objlist':
                # TODO: detach prev children.
                # TODO: use object wrapper that knows about listeners
                l = ObjectList(prop_name, obj)
                for child_id in value:
                    child = self._object_map[child_id]
                    l.append(child)
                obj.set_attribute(prop_name, l)
            else:
                raise ValueError(
                    "Property type %s not supported." % prop_type)

    def handle_project_mutation(self, mutation):
        logger.info("Mutation received: %s" % mutation)
        try:
            if isinstance(mutation, mutations.SetProperties):
                obj = self._object_map[mutation.id]
                self.apply_properties(obj, mutation.properties)

            elif isinstance(mutation, mutations.AddObject):
                obj = ObjectProxy(mutation.id, mutation.cls)
                self.apply_properties(obj, mutation.properties)
                self._object_map[mutation.id] = obj

            elif isinstance(mutation, mutations.UpdateObjectList):
                obj = self._object_map[mutation.id]
                lst = getattr(obj, mutation.prop_name)
                if mutation.args[0] == 'insert':
                    idx, child_id = mutation.args[1:]
                    child = self._object_map[child_id]
                    child.parent = obj
                    lst.insert(idx, child)
                else:
                    raise ValueError(mutation.args[0])
            else:
                raise ValueError("Unknown mutation %s received." % mutation)
        except Exception as exc:
            logger.exception("Handling of mutation %s failed:", mutation)

    def handle_project_closed(self):
        logger.info("Project closed received.")

    async def shutdown(self):
        await self._stub.call('SHUTDOWN')

    async def test(self):
        await self._stub.call('TEST')

    async def create(self, path):
        assert self.project is None
        root_id = await self._stub.call('CREATE', path)
        self.__set_project(root_id)

    async def create_inmemory(self):
        assert self.project is None
        root_id = await self._stub.call('CREATE_INMEMORY')
        self.__set_project(root_id)

    async def open(self, path):
        assert self.project is None
        root_id = await self._stub.call('OPEN', path)
        self.__set_project(root_id)

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


class ProjectClient(ProjectClientMixin, ProjectClientBase):
    pass
