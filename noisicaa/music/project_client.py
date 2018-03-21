#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

# TODO: pylint-unclean

from fractions import Fraction
import getpass
import logging
import socket

from noisicaa import audioproc
from noisicaa import core
from noisicaa.core import ipc

from . import mutations

logger = logging.getLogger(__name__)


class ObjectProxy(core.ObjectBase):
    def __init__(self, *, obj_id, **kwargs):
        super().__init__(**kwargs)
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

        else:
            raise TypeError("Unsupported change type %s" % type(change))


class ProjectClientBase(object):
    def __init__(self, event_loop, tmp_dir):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client', socket_dir=tmp_dir)

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
        self._session_data = {}
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
            'PROJECT_MUTATIONS', self.handle_project_mutations)
        self.server.add_command_handler(
            'PROJECT_CLOSED', self.handle_project_closed)
        self.server.add_command_handler(
            'PLAYER_STATUS', self.handle_player_status,
            log_level=-1)
        self.server.add_command_handler(
            'SESSION_DATA_MUTATION', self.handle_session_data_mutation)

    async def cleanup(self):
        await self.disconnect()
        await super().cleanup()

    async def connect(self, address):
        assert self._stub is None
        self._stub = ipc.Stub(self.event_loop, address)
        await self._stub.connect()
        self._session_data = {}
        session_name = '%s.%s' % (getpass.getuser(), socket.getfqdn())
        self._session_id = await self._stub.call('START_SESSION', self.server.address, session_name)
        root_id = await self._stub.call('GET_ROOT_ID', self._session_id)
        if root_id is not None:
            # Connected to a loaded project.
            self.__set_project(root_id)

    async def disconnect(self, shutdown=False):
        if self._session_id is not None:
            try:
                await self._stub.call('END_SESSION', self._session_id)
            except ipc.ConnectionClosed:
                logger.info("Connection already closed.")
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

    def handle_project_mutations(self, mutations):
        for mutation in mutations:
            self.handle_project_mutation(mutation)

    def handle_project_mutation(self, mutation):
        logger.info("Mutation received: %s", mutation)

        if isinstance(mutation, mutations.SetProperties):
            obj = self._object_map[mutation.id]
            assert not isinstance(obj, core.DeferredReference)
            self.apply_properties(obj, mutation.properties)

        elif isinstance(mutation, mutations.AddObject):
            cls = self.cls_map[mutation.cls]
            obj = cls(obj_id=mutation.id)
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
        root_id = await self._stub.call('CREATE', self._session_id, path)
        self.__set_project(root_id)

    async def create_inmemory(self):
        assert self.project is None
        root_id = await self._stub.call('CREATE_INMEMORY', self._session_id)
        self.__set_project(root_id)

    async def open(self, path):
        assert self.project is None
        root_id = await self._stub.call('OPEN', self._session_id, path)
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

    async def create_player(self, *, audioproc_address):
        return await self._stub.call(
            'CREATE_PLAYER', self._session_id,
            client_address=self.server.address,
            audioproc_address=audioproc_address)

    async def delete_player(self, player_id):
        return await self._stub.call('DELETE_PLAYER', self._session_id, player_id)

    async def create_plugin_ui(self, player_id, node_id):
        return await self._stub.call('CREATE_PLUGIN_UI', self._session_id, player_id, node_id)

    async def delete_plugin_ui(self, player_id, node_id):
        return await self._stub.call('DELETE_PLUGIN_UI', self._session_id, player_id, node_id)

    async def update_player_state(self, player_id, state):
        return await self._stub.call('UPDATE_PLAYER_STATE', self._session_id, player_id, state)

    async def player_send_message(self, player_id, msg):
        return await self._stub.call(
            'PLAYER_SEND_MESSAGE', self._session_id, player_id, msg.to_bytes())

    async def restart_player_pipeline(self, player_id):
        return await self._stub.call('RESTART_PLAYER_PIPELINE', self._session_id, player_id)

    def add_player_status_listener(self, player_id, callback):
        return self.listeners.add('player_status:%s' % player_id, callback)

    async def handle_player_status(self, player_id, args):
        self.listeners.call('player_status:%s' % player_id, **args)

    async def dump(self):
        await self._stub.call('DUMP', self._session_id)

    async def render(self, callback_address, render_settings):
        await self._stub.call('RENDER', self._session_id, callback_address, render_settings)

    async def handle_session_data_mutation(self, data):
        for key, value in data.items():
            if key not in self._session_data or self._session_data[key] != value:
                self._session_data[key] = value
                self.listeners.call('session_data:%s' % key, value)

    def set_session_values(self, data):
        assert isinstance(data, dict), data
        for key, value in data.items():
            assert isinstance(key, str), key
            assert isinstance(value, (str, bytes, bool, int, float, Fraction, audioproc.MusicalTime, audioproc.MusicalDuration)), value

        self._session_data.update(data)
        self.event_loop.create_task(
            self._stub.call('SET_SESSION_VALUES', self._session_id, data))

    def get_session_value(self, key, default):
        return self._session_data.get(key, default)


class ProjectClient(ProjectClientMixin, ProjectClientBase):
    pass
