#!/usr/bin/python3

import asyncio
import logging

from noisicaa import core
from noisicaa.core import ipc

from . import mutations
from . import model

logger = logging.getLogger(__name__)


class ObjectProxy(core.ObjectBase):
    def __init__(self, obj_id):
        super().__init__()
        self.state['id'] = obj_id
        self.listeners = core.CallbackRegistry()

    def property_changed(self, change):
        if isinstance(change, core.PropertyValueChange):
            self.listeners.call(
                change.prop_name, change.old_value, change.new_value)

        elif isinstance(change, core.PropertyListInsert):
            self.listeners.call(
                change.prop_name, 'insert',
                change.index, change.new_value)

        elif isinstance(change, core.PropertyListDelete):
            self.listeners.call(
                change.prop_name, 'delete',
                change.index, change.old_value)

        elif isinstance(change, core.PropertyListClear):
            self.listeners.call(change.prop_name, 'clear')

        else:
            raise TypeError("Unsupported change type %s" % type(change))


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
    def __init__(self, *args, node_db=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._node_db = node_db
        self._stub = None
        self._session_id = None
        self._object_map = {}
        self.project = None
        self.cls_map = {}
        self.listeners = core.CallbackRegistry()

    def __set_project(self, root_id):
        assert self.project is None
        self.project = self._object_map[root_id]
        self.project.init(self._node_db, self._object_map)

    async def setup(self):
        await super().setup()
        self.server.add_command_handler(
            'PROJECT_MUTATION', self.handle_project_mutation)
        self.server.add_command_handler(
            'PROJECT_CLOSED', self.handle_project_closed)
        self.server.add_command_handler(
            'PLAYER_STATUS', self.handle_player_status,
            log_level=-1)

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_id, root_id = await self._stub.call(
            'START_SESSION', self.server.address)
        if root_id is not None:
            # Connected to a loaded project.
            self.__set_project(root_id)

    async def disconnect(self, shutdown=False):
        if self._session_id is not None:
            await self._stub.call('END_SESSION', self._session_id)
            self._session_id = None

        if self._stub is not None:
            if shutdown:
                await self.shutdown()

            await self._stub.close()
            self._stub = None

    def apply_properties(self, obj, properties):
        for prop_name, prop_type, value in properties:
            if prop_type == 'scalar':
                setattr(obj, prop_name, value)

            elif prop_type == 'list':
                lst = getattr(obj, prop_name)
                lst.clear()
                lst.extend(value)

            elif prop_type == 'obj':
                child = None
                if value is not None:
                    child = self._object_map[value]
                setattr(obj, prop_name, child)

            elif prop_type == 'objref':
                child = None
                if value is not None:
                    try:
                        child = self._object_map[value]
                    except KeyError:
                        child = core.DeferredReference(value)
                        self._object_map[value] = child
                    if isinstance(child, core.DeferredReference):
                        child.add_reference(
                            obj, obj.get_property(prop_name))
                setattr(obj, prop_name, child)

            elif prop_type == 'objlist':
                lst = getattr(obj, prop_name)
                lst.clear()
                for child_id in value:
                    child = self._object_map[child_id]
                    lst.append(child)

            else:
                raise ValueError(
                    "Property type %s not supported." % prop_type)

    def handle_project_mutation(self, mutation):
        logger.info("Mutation received: %s" % mutation)

        if isinstance(mutation, mutations.SetProperties):
            obj = self._object_map[mutation.id]
            assert not isinstance(obj, core.DeferredReference)
            self.apply_properties(obj, mutation.properties)

        elif isinstance(mutation, mutations.AddObject):
            cls = self.cls_map[mutation.cls]
            obj = cls(mutation.id)
            self.apply_properties(obj, mutation.properties)
            # TODO: We should assert that mutation.id is either not
            # in _object_map or points at a DeferredReference.
            # But we don't delete entries from _object_map when
            # objects are removed, so we leave zombies behind, which
            # we just override here.
            if (mutation.id in self._object_map
                and isinstance(
                    self._object_map[mutation.id],
                    core.DeferredReference)):
                self._object_map[mutation.id].dereference(obj)
            self._object_map[mutation.id] = obj

        elif isinstance(mutation, mutations.ListInsert):
            obj = self._object_map[mutation.id]
            lst = getattr(obj, mutation.prop_name)
            if mutation.value_type == 'obj':
                child = self._object_map[mutation.value]
                lst.insert(mutation.index, child)
            elif mutation.value_type == 'scalar':
                lst.insert(mutation.index, mutation.value)
            else:
                raise ValueError(
                    "Value type %s not supported."
                    % mutation.value_type)

        elif isinstance(mutation, mutations.ListDelete):
            obj = self._object_map[mutation.id]
            lst = getattr(obj, mutation.prop_name)
            del lst[mutation.index]

        else:
            raise ValueError("Unknown mutation %s received." % mutation)

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

    async def undo(self):
        assert self.project is not None
        await self._stub.call('UNDO')

    async def redo(self):
        assert self.project is not None
        await self._stub.call('REDO')

    async def serialize(self, obj_id):
        assert self.project is not None
        return await self._stub.call('SERIALIZE', self._session_id, obj_id)

    async def create_player(self, sheet_id):
        return await self._stub.call(
            'CREATE_PLAYER', self._session_id,
            self.server.address, sheet_id)

    async def get_player_audioproc_address(self, player_id):
        return await self._stub.call(
            'GET_PLAYER_AUDIOPROC_ADDRESS', self._session_id, player_id)

    async def delete_player(self, player_id):
        return await self._stub.call(
            'DELETE_PLAYER', self._session_id, player_id)

    async def player_start(self, player_id):
        return await self._stub.call(
            'PLAYER_START', self._session_id, player_id)

    async def player_pause(self, player_id):
        return await self._stub.call(
            'PLAYER_PAUSE', self._session_id, player_id)

    async def player_stop(self, player_id):
        return await self._stub.call(
            'PLAYER_STOP', self._session_id, player_id)

    def add_player_status_listener(self, player_id, callback):
        return self.listeners.add(
            'player_status:%s' % player_id, callback)

    async def handle_player_status(self, player_id, args):
        self.listeners.call('player_status:%s' % player_id, **args)

    async def dump(self):
        await self._stub.call('DUMP', self._session_id)

class ProjectClient(ProjectClientMixin, ProjectClientBase):
    pass
