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
import cProfile

import toposort

from noisicaa import core
from noisicaa.bindings import lv2
from noisicaa.core import ipc
from noisicaa.core.status cimport check
from noisicaa.core.perf_stats cimport PyPerfStats
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import player_state_pb2
from . cimport realm as realm_lib
from .spec cimport PySpec
from .block_context cimport PyBlockContext
from .backend cimport PyBackend, PyBackendSettings
from . cimport message_queue
from .player cimport PyPlayer
from . import buffers
from . import graph

logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class DuplicateRealmName(Error):
    pass

class RealmNotFound(Error):
    pass

class DuplicateRootRealm(Error):
    pass


class Engine(object):
    def __init__(
            self, *,
            host_system, event_loop, manager, server_address,
            shm=None, profile_path=None):
        self.listeners = core.CallbackRegistry()

        self.__host_system = host_system
        self.__event_loop = event_loop
        self.__manager = manager
        self.__server_address = server_address
        self.__shm = shm
        self.__profile_path = profile_path

        self.__realms = {}
        self.__root_realm = None
        self.__realm_listeners = {}
        self.__backend = None

        self.__backend_ready = threading.Event()
        self.__backend_released = threading.Event()

        self.__engine_thread = None
        self.__engine_started = None
        self.__engine_exit = None

        self.__maintenance_task = None
        self.__plugin_host = None

        self.__bpm = 120
        self.__duration = musical_time.PyMusicalDuration(2, 1)

        self.notification_listener = core.CallbackRegistry()

    def dump(self):
        # TODO: reimplement
        pass

    async def setup(self, *, start_thread=True):
        self.__engine_started = threading.Event()
        self.__engine_exit = threading.Event()
        if start_thread:
            self.__engine_thread = threading.Thread(target=self.engine_main)
            self.__engine_thread.start()
            logger.info("Starting engine thread (%s)...", self.__engine_thread.ident)
            self.__engine_started.wait()

            logger.info("Starting maintenance task...")
            self.__maintenance_task = self.__event_loop.create_task(self.__maintenance_task_main())

        logger.info("Engine up and running.")

    async def cleanup(self):
        if self.__backend is not None:
            logger.info("Stopping backend...")
            self.__backend.stop()

        if self.__maintenance_task is not None:
            logger.info("Shutting down maintenance task...")
            self.__maintenance_task.cancel()
            self.__maintenance_task = None

        if self.__engine_thread is not None:  # pragma: no branch
            logger.info("Shutting down engine thread...")
            self.__engine_exit.set()
            self.__engine_thread.join()
            self.__engine_thread = None
            logger.info("Engine thread stopped.")

        if self.__backend is not None:
            self.__backend.cleanup()
            self.__backend = None

        if self.__plugin_host is not None:
            logger.info("Shutting down plugin host process...")
            try:
                await self.__plugin_host.call('SHUTDOWN')
            except ipc.ConnectionClosed:
                logger.info("Connection to plugin host process already closed.")
            await self.__plugin_host.close()
            self.__plugin_host = None
            logger.info("Plugin host process stopped.")

        self.__engine_started = None
        self.__engine_exit = None

        for realm in self.__realms.values():
            await realm.cleanup()
        self.__realms.clear()
        self.__root_realm = None

        for listener in self.__realm_listeners.values():
            listener.remove()
        self.__realm_listeners.clear()

    async def get_plugin_host(self):
        if self.__plugin_host is None:
            address = await self.__manager.call(
                'CREATE_PLUGIN_HOST_PROCESS', audioproc_address=self.__server_address)
            self.__plugin_host = ipc.Stub(self.__event_loop, address)
            await self.__plugin_host.connect()

        return self.__plugin_host

    async def create_plugin_ui(self, realm, node_id):
        return await self.__plugin_host.call('CREATE_UI', realm, node_id)

    async def delete_plugin_ui(self, realm, node_id):
        return await self.__plugin_host.call('DELETE_UI', realm, node_id)

    def get_realm(self, name: str) -> realm_lib.PyRealm:
        try:
            return self.__realms[name]
        except KeyError as exc:
            raise RealmNotFound("Realm '%s' does not exist" % name) from exc

    async def create_realm(self, *, name: str, parent: str, enable_player: bool = False):
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
            player = PyPlayer(self.__host_system)
            player.listeners.add(
                'player_state',
                functools.partial(self.listeners.call, 'player_state', name))

        else:
            logger.info("Player disabled.")
            player = None

        realm = realm_lib.PyRealm(
            engine=self,
            name=name,
            parent=parent_realm,
            host_system=self.__host_system,
            player=player)
        self.__realms[name] = realm
        self.__realm_listeners['%s:node_state_changed' % name] = realm.listeners.add(
            'node_state_changed',
            functools.partial(self.listeners.call, 'node_state', name))
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
        self.__realm_listeners.pop('%s:node_state_changed' % name).remove()
        await realm.cleanup()

    def get_buffer(self, name, type):
        return self.__root_realm.get_buffer(name, type)

    async def set_host_parameters(self, *, block_size=None, sample_rate=None):
        reinit = False
        if block_size is not None and block_size != self.__host_system.block_size:
            reinit = True
        if sample_rate is not None and sample_rate != self.__host_system.sample_rate:
            reinit = True

        if reinit:
            logger.info("Reinitializing engine...")

            if self.__backend is not None:
                logger.info("Stopping backend...")
                self.__backend.stop()

            if self.__maintenance_task is not None:
                logger.info("Shutting down maintenance task...")
                self.__maintenance_task.cancel()
                self.__maintenance_task = None

            if self.__engine_thread is not None:  # pragma: no branch
                logger.info("Shutting down engine thread...")
                self.__engine_exit.set()
                self.__engine_thread.join()
                self.__engine_thread = None
                logger.info("Engine thread stopped.")
            self.__engine_started = None
            self.__engine_exit = None

            if self.__backend is not None:
                self.__backend.cleanup()

            for realm in self.__realms.values():
                logger.info("Clearing realm '%s'...", realm.name)
                for node in realm.graph.nodes:
                    await node.cleanup()
                realm.clear_programs()

            if self.__plugin_host is not None:
                logger.info("Shutting down plugin host process...")
                try:
                    await self.__plugin_host.call('SHUTDOWN')
                except ipc.ConnectionClosed:
                    logger.info("Connection to plugin host process already closed.")
                await self.__plugin_host.close()
                self.__plugin_host = None
                logger.info("Plugin host process stopped.")

            logger.info("Shutting down host system...")
            self.__host_system.cleanup()

            logger.info("Engine stopped, changing host parameters...")

            if block_size is not None:
                self.__host_system.set_block_size(block_size)
            if sample_rate is not None:
                self.__host_system.set_sample_rate(sample_rate)

            logger.info("Restarting engine...")

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
                self.__backend_ready.set()

            self.__engine_started = threading.Event()
            self.__engine_exit = threading.Event()
            self.__engine_thread = threading.Thread(target=self.engine_main)
            self.__engine_thread.start()
            logger.info("Starting engine thread (%s)...", self.__engine_thread.ident)
            self.__engine_started.wait()

            logger.info("Starting maintenance task...")
            self.__maintenance_task = self.__event_loop.create_task(self.__maintenance_task_main())

            logger.info("Engine reinitialized.")

    def set_backend(self, name, **parameters):
        assert self.__root_realm is not None

        if self.__backend is not None:
            self.__backend.release()
            self.__backend_released.wait()
            self.__backend_released.clear()

            self.__backend.cleanup()
            self.__backend = None

        settings = PyBackendSettings(**parameters)
        self.__backend = PyBackend(self.__host_system, name, settings)
        self.__backend.setup(self.__root_realm)
        self.__backend_ready.set()

    def set_backend_parameters(self):
        if self.__backend is not None:
            pass

    def send_message(self, msg):
        if self.__backend is not None:
            self.__backend.send_message(msg)

    def engine_main(self):
        profiler = None
        try:
            logger.info("Starting engine...")

            self.__engine_started.set()

            if self.__profile_path:
                profiler = cProfile.Profile()
                profiler.enable()
            try:
                self.engine_loop()
            finally:
                if profiler is not None:
                    profiler.disable()
                    profiler.dump_stats(self.__profile_path)

        except:  # pragma: no coverage  # pylint: disable=bare-except
            sys.stdout.flush()
            sys.excepthook(*sys.exc_info())
            sys.stderr.flush()
            time.sleep(0.2)
            os._exit(1)  # pylint: disable=protected-access

        finally:
            logger.info("Engine finished.")

    def engine_loop(self):
        backend = None
        cdef message_queue.MessageQueue* out_messages
        cdef message_queue.Message* msg
        cdef realm_lib.PyProgram program
        cdef PyBlockContext ctxt

        while True:
            if self.__engine_exit.is_set():
                logger.info("Exiting engine mainloop.")
                break

            if backend is None:
                if self.__backend_ready.wait(0.1):
                    self.__backend_ready.clear()
                    assert self.__backend is not None
                    backend = self.__backend
                else:
                    continue

            elif backend.released():
                backend = None
                self.__backend_released.set()
                continue

            if backend.stopped():
                logger.info("Backend stopped, exiting engine mainloop.")
                break

            ctxt = self.__root_realm.block_context

            if len(ctxt.perf) > 0:
                self.listeners.call('perf_data', ctxt.perf.serialize())
            ctxt.perf.reset()

            program = self.__root_realm.get_active_program()
            if program is None:
                time.sleep(0.1)
                continue

            backend.begin_block(ctxt)
            try:
                self.__root_realm.process_block(program)

                for channel in ('left', 'right'):
                    sink_buf = self.__root_realm.get_buffer('sink:in:' + channel, buffers.PyFloatAudioBlock())
                    backend.output(ctxt, channel, sink_buf)

            finally:
                backend.end_block(ctxt)

            out_messages = ctxt.get().out_messages.get()
            msg = out_messages.first()
            while not out_messages.is_end(msg):
                if msg.type == message_queue.MessageType.SOUND_FILE_COMPLETE:
                    node_id = bytes((<message_queue.SoundFileCompleteMessage*>msg).node_id).decode('utf-8')
                    self.notification_listener.call(node_id, msg.type)

                elif msg.type == message_queue.MessageType.PORT_RMS:
                    node_id = bytes(
                        (<message_queue.PortRMSMessage*>msg).node_id).decode('utf-8')
                    port_index = (<message_queue.PortRMSMessage*>msg).port_index
                    rms = (<message_queue.PortRMSMessage*>msg).rms

                    logger.debug("%s:%d = %f", node_id, port_index, rms)

                else:
                    logger.debug("out message %d", msg.type)

                msg = out_messages.next(msg)
            out_messages.clear()

    async def __maintenance_task_main(self):
        while True:
            logger.debug("Running maintenance task...")
            for realm in self.__realms.values():
                realm.run_maintenance()
            await asyncio.sleep(0.2, loop=self.__event_loop)
