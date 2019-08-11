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

from libcpp.string cimport string
from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore

import asyncio
import enum
import functools
import logging
import math
import os
import random
import sys
import threading
import time

import toposort

from noisicaa import core
from noisicaa import editor_main_pb2
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.core.status cimport check
from noisicaa.core.perf_stats cimport PyPerfStats
from noisicaa.host_system.host_system cimport PyHostSystem
from noisicaa.audioproc.public import engine_notification_pb2
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import player_state_pb2
from noisicaa.audioproc.public import backend_settings_pb2
from .realm cimport PyRealm
from .spec cimport PySpec
from .block_context cimport PyBlockContext
from .backend cimport PyBackend
from . cimport message_queue
from .player cimport PyPlayer
from . import buffers
from . import graph
from . import plugin_host_pb2

logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class DuplicateRealmName(Error):
    pass

class RealmNotFound(Error):
    pass

class DuplicateRootRealm(Error):
    pass


cdef class PyEngine(object):
    cdef dict __dict__
    cdef unique_ptr[Engine] __engine_ptr
    cdef Engine* __engine
    cdef PyHostSystem __host_system
    cdef PyRealm __root_realm

    def __init__(
            self, *,
            PyHostSystem host_system, event_loop, manager, server_address, shm=None):
        self.notifications = core.Callback()

        self.__engine = NULL
        self.__host_system = host_system
        self.__event_loop = event_loop
        self.__manager = manager
        self.__server_address = server_address
        self.__shm = shm

        self.__realms = {}
        self.__root_realm = None
        self.__realm_listeners = {}
        self.__backend = None
        self.__backend_listeners = {}

        self.__engine_thread = None
        self.__engine_started = None

        self.__maintenance_task = None
        self.__plugin_host_address = None
        self.__plugin_host = None

        self.__bpm = 120
        self.__duration = musical_time.PyMusicalDuration(2, 1)

    def __set_state(self, state: engine_notification_pb2.EngineStateChange.State) -> None:
        self.notifications.call(engine_notification_pb2.EngineNotification(
            engine_state_changes=[engine_notification_pb2.EngineStateChange(
                state=state)]))

    async def setup(self, *):
        self.__set_state(engine_notification_pb2.EngineStateChange.SETUP)

        self.__engine_ptr.reset(new Engine(
            self.__host_system.get(), self.__notification_callback, <PyObject*>self))
        self.__engine = self.__engine_ptr.get()
        with nogil:
            check(self.__engine.setup())

    async def cleanup(self):
        self.__set_state(engine_notification_pb2.EngineStateChange.CLEANUP)

        await self.stop_engine()
        self.stop_backend()

        if self.__plugin_host is not None:
            logger.info("Disconnecting from plugin host process...")
            await self.__plugin_host.close()
            self.__plugin_host = None

        if self.__plugin_host_address is not None:
            logger.info("Shutting down plugin host process...")
            await self.__manager.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.__plugin_host_address))
            logger.info("Plugin host process stopped.")

        for realm in self.__realms.values():
            await realm.cleanup()
        self.__realms.clear()
        self.__root_realm = None

        for listener in self.__realm_listeners.values():
            listener.remove()
        self.__realm_listeners.clear()

        if self.__engine != NULL:
            with nogil:
                self.__engine.cleanup()
            self.__engine_ptr.release()
            self.__engine = NULL

        self.__set_state(engine_notification_pb2.EngineStateChange.STOPPED)

    def stop_backend(self):
        if self.__backend is not None:
            self.__backend.cleanup()
            self.__backend = None

        for listener in self.__backend_listeners.values():
            listener.remove()
        self.__backend_listeners.clear()

    async def start_engine(self):
        assert self.__root_realm is not None
        assert self.__backend is not None

        self.__engine_started = threading.Event()

        self.__engine_thread = threading.Thread(target=self.engine_main)
        self.__engine_thread.start()
        logger.info("Starting engine thread (%s)...", self.__engine_thread.ident)
        self.__engine_started.wait()

        logger.info("Starting maintenance task...")
        self.__maintenance_task = self.__event_loop.create_task(self.__maintenance_task_main())

    async def stop_engine(self):
        if self.__maintenance_task is not None:
            logger.info("Shutting down maintenance task...")
            if not self.__maintenance_task.done():
                self.__maintenance_task.cancel()
            try:
                await self.__maintenance_task
            except asyncio.CancelledError:
                pass
            self.__maintenance_task = None

        if self.__engine_thread is not None:  # pragma: no branch
            logger.info("Shutting down engine thread...")
            self.__engine.exit_loop()
            self.__engine_thread.join()
            self.__engine_thread = None
            logger.info("Engine thread stopped.")

        self.__engine_started = None

    def dump(self):
        out = ""
        for _, realm in sorted(self.__realms.items()):
            out += realm.dump()
        return out

    async def get_plugin_host(self):
        if self.__plugin_host is None:
            create_plugin_host_response = editor_main_pb2.CreateProcessResponse()
            await self.__manager.call(
                'CREATE_PLUGIN_HOST_PROCESS', None, create_plugin_host_response)
            self.__plugin_host_address = create_plugin_host_response.address

            self.__plugin_host = ipc.Stub(self.__event_loop, self.__plugin_host_address)
            await self.__plugin_host.connect()

        return self.__plugin_host

    async def create_plugin_ui(self, realm, node_id):
        request = plugin_host_pb2.CreatePluginUIRequest(
            realm=realm,
            node_id=node_id)
        response = plugin_host_pb2.CreatePluginUIResponse()
        await self.__plugin_host.call('CREATE_UI', request, response)
        return (response.wid, (response.width, response.height))

    async def delete_plugin_ui(self, realm, node_id):
        await self.__plugin_host.call(
            'DELETE_UI',
            plugin_host_pb2.DeletePluginUIRequest(
                realm=realm,
                node_id=node_id))

    def get_realm(self, name: str) -> PyRealm:
        try:
            return self.__realms[name]
        except KeyError as exc:
            raise RealmNotFound("Realm '%s' does not exist" % name) from exc

    async def create_realm(
            self, *,
            name: str, parent: str, enable_player: bool = False, callback_address: str = None
    ):
        if name in self.__realms:
            raise DuplicateRealmName("Realm '%s' already exists" % name)

        if parent is not None:
            parent_realm = self.get_realm(parent)
        else:
            if self.__root_realm is not None:
                raise DuplicateRootRealm("Root realm already set.")
            parent_realm = None

        logger.info("Creating realm '%s'...", name)

        if enable_player:
            logger.info("Enabling player...")
            player = PyPlayer(self.__host_system, name)

        else:
            logger.info("Player disabled.")
            player = None

        cdef PyRealm realm = PyRealm(
            engine=self,
            name=name,
            parent=parent_realm,
            host_system=self.__host_system,
            player=player,
            callback_address=callback_address)
        self.__realms[name] = realm
        self.__realm_listeners['%s:notifications' % name] = realm.notifications.add(
            self.notifications.call)

        if parent is None:
            self.__root_realm = realm
        else:
            parent_realm.child_realms[name] = realm

        await realm.setup()
        return realm

    async def delete_realm(self, name):
        realm = self.get_realm(name)

        logger.info("Deleting realm '%s'...", name)
        if realm.parent is not None:
            realm.parent.child_realms.pop(name)
        del self.__realms[name]
        self.__realm_listeners.pop('%s:notifications' % name).remove()
        await realm.cleanup()

    def get_buffer(self, name, type):
        return self.__root_realm.get_buffer(name, type)

    async def set_host_parameters(self, parameters):
        reinit = False
        if (parameters.HasField('block_size')
                and parameters.block_size != self.__host_system.block_size):
            reinit = True
        if (parameters.HasField('sample_rate')
                and parameters.sample_rate != self.__host_system.sample_rate):
            reinit = True

        if reinit:
            logger.info("Reinitializing engine...")
            self.__set_state(engine_notification_pb2.EngineStateChange.CLEANUP)

            await self.stop_engine()

            if self.__backend is not None:
                self.__backend.cleanup()

            for realm in self.__realms.values():
                logger.info("Clearing realm '%s'...", realm.name)
                for node in realm.graph.nodes:
                    await node.cleanup()
                realm.clear_programs()

            if self.__plugin_host is not None:
                logger.info("Disconnecting from plugin host process...")
                await self.__plugin_host.close()
                self.__plugin_host = None

            if self.__plugin_host_address is not None:
                logger.info("Shutting down plugin host process...")
                await self.__manager.call(
                    'SHUTDOWN_PROCESS',
                    editor_main_pb2.ShutdownProcessRequest(
                        address=self.__plugin_host_address))
                logger.info("Plugin host process stopped.")

            logger.info("Shutting down host system...")
            self.__host_system.cleanup()

            logger.info("Engine stopped, changing host parameters...")
            self.__set_state(engine_notification_pb2.EngineStateChange.STOPPED)

            if parameters.HasField('block_size'):
                self.__host_system.set_block_size(parameters.block_size)
            if parameters.HasField('sample_rate'):
                self.__host_system.set_sample_rate(parameters.sample_rate)

            logger.info("Restarting engine...")
            self.__set_state(engine_notification_pb2.EngineStateChange.SETUP)

            logger.info("Restarting host system...")
            self.__host_system.setup()

            for realm in self.__realms.values():
                logger.info("Restarting realm '%s'...", realm.name)
                for node in realm.graph.nodes:
                    await realm.setup_node(node)
                realm.update_spec()

            if self.__backend is not None:
                logger.info("Restarting backend...")
                self.__backend.setup(self.__root_realm)

            await self.start_engine()

            logger.info("Engine reinitialized.")
            self.__set_state(engine_notification_pb2.EngineStateChange.RUNNING)

    async def set_backend(self, name, settings=None):
        assert self.__root_realm is not None

        if self.__backend is not None:
            self.__set_state(engine_notification_pb2.EngineStateChange.CLEANUP)

            await self.stop_engine()
            self.stop_backend()

            self.__set_state(engine_notification_pb2.EngineStateChange.SETUP)

        if settings is None:
            settings = backend_settings_pb2.BackendSettings()
        self.__backend = PyBackend(self.__host_system, name, settings)
        self.__backend_listeners['notifications'] = self.__backend.notifications.add(
            self.notifications.call)
        self.__backend.setup(self.__root_realm)

        logger.info("Backend '%s' ready.", name)

        await self.start_engine()

        logger.info("Engine up and running.")
        self.__set_state(engine_notification_pb2.EngineStateChange.RUNNING)

    @staticmethod
    cdef void __notification_callback(void* c_self, const string& notification_serialized) with gil:
        self = <object><PyObject*>c_self

        # Have to stash away any active exception, because otherwise exception handling
        # might get confused.
        # See https://github.com/cython/cython/issues/1877
        cdef PyObject* exc_type
        cdef PyObject* exc_value
        cdef PyObject* exc_trackback
        PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)
        try:
            notification = engine_notification_pb2.EngineNotification()
            notification.ParseFromString(notification_serialized)
            self.notifications.call(notification)

        finally:
            PyErr_Restore(exc_type, exc_value, exc_trackback)

    def engine_main(self):
        cdef PyBackend backend = self.__backend
        cdef PyRealm realm = self.__root_realm

        try:
            logger.info("Starting engine...")

            with core.RTSafeLogging():
                check(self.__engine.setup_thread())

                self.__engine_started.set()
                with nogil:
                    check(self.__engine.loop(realm.get(), backend.get()))


        except:  # pragma: no coverage  # pylint: disable=bare-except
            sys.stdout.flush()
            sys.excepthook(*sys.exc_info())
            sys.stderr.flush()
            time.sleep(0.2)
            os._exit(1)  # pylint: disable=protected-access

        finally:
            logger.info("Engine finished.")

    async def __maintenance_task_main(self):
        while True:
            logger.debug("Running maintenance task...")
            for realm in self.__realms.values():
                realm.run_maintenance()
            await asyncio.sleep(0.2, loop=self.__event_loop)
