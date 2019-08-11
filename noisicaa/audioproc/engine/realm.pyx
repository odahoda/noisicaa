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

from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore
from libc.stdint cimport uint8_t, uint32_t
from libc.string cimport memmove
from libcpp.string cimport string

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.core import empty_message_pb2
from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from noisicaa.audioproc.public import engine_notification_pb2
from .player cimport PyPlayer
from .spec cimport PySpec
from .processor cimport PyProcessor
from .control_value cimport PyControlValue
from .block_context cimport PyBlockContext
from .buffers cimport Buffer, PyBufferType
from . import processor
from . import graph
from . import plugin_host_pb2

logger = logging.getLogger(__name__)


cdef class PyProgram(object):
    cdef void set(self, Program* program) nogil:
        self.__program = program

    cdef Program* get(self) nogil:
        return self.__program


cdef class PyRealm(object):
    def __init__(
            self, *,
            engine,
            str name,
            PyRealm parent,
            PyHostSystem host_system,
            PyPlayer player,
            str callback_address):
        self.notifications = core.Callback()

        self.__engine = engine
        self.__name = name
        self.__parent = parent
        self.__host_system = host_system
        self.__player = player
        self.__callback_address = callback_address

        self.__bpm = 120
        self.__duration = audioproc.MusicalDuration(4, 1)
        self.__graph = graph.Graph(self)

        self.child_realms = {}

        cdef string c_name = name.encode('utf-8')
        cdef Player* c_player = NULL
        if player is not None:
            c_player = player.get()
        self.__realm = new Realm(c_name, host_system.get(), c_player)
        self.__realm.incref()

        self.__realm.set_notification_callback(
            self.__notification_callback, <PyObject*>self)

        self.__sink = graph.Node.create(
            host_system=self.__host_system,
            description=node_db.Builtins.RealmSinkDescription)
        self.__graph.add_node(self.__sink)

    cdef Realm* get(self) nogil:
        return self.__realm

    @property
    def name(self):
        return self.__name

    @property
    def parent(self):
        return self.__parent

    @property
    def graph(self):
        return self.__graph

    @property
    def player(self):
        return self.__player

    @property
    def callback_address(self):
        return self.__callback_address

    @property
    def block_context(self):
        return PyBlockContext.create(self.__realm.block_context())

    async def setup(self):
        logger.info("Setting up realm '%s'...", self.name)

        await self.setup_node(self.__sink)

        with nogil:
            check(self.__realm.setup())

        logger.info("Realm '%s' set up.", self.name)

    async def cleanup(self):
        logger.info("Cleaning up realm '%s'...", self.name)

        await self.__sink.cleanup()

        if self.__realm != NULL:
            with nogil:
                self.__realm.decref()
                self.__realm = NULL

        logger.info("Realm '%s' cleaned up.", self.name)

    def dump(self):
        cdef string out
        with nogil:
            out = self.__realm.dump()
        return out.decode('ascii')

    def clear_programs(self):
        with nogil:
            self.__realm.clear_programs()

    def get_buffer(self, str name, PyBufferType type):
        cdef bytes b_name = name.encode('ascii')
        cdef Buffer* buf = self.__realm.get_buffer(b_name)
        assert buf != NULL, name
        cdef int size = type.get().size(self.__host_system.get())
        return memoryview(<uint8_t[:size]>buf.data()).cast(type.view_type)

    async def get_plugin_host(self):
        return await self.__engine.get_plugin_host()

    def update_spec(self):
        self.set_spec(self.__graph.compile(self.__bpm, self.__duration))

    def set_spec(self, PySpec spec):
        logger.debug("set_spec:\n%s", spec.dump())
        with nogil:
            check(self.__realm.set_spec(spec.release()))

    async def setup_node(self, node):
        assert node.is_owned_by(self), node.id

        # TODO: reanimate crash handling
        # if node.id == self._crasher_id:
        #     logger.warning(
        #         "Node %s (%s) has been deactivated, because it crashed the pipeline.",
        #         node.id, type(node).__name__)
        #     self.listeners.call('node_state', node.id, broken=True)
        #     node.broken = True
        #     return

        # if self._shm_data is not None:
        #     marker = node.id.encode('ascii') + b'\0'
        #     self._shm_data[512:512+len(marker)] = marker
        await node.setup()
        # if self._shm_data is not None:
        #     self._shm_data[512] = 0

    def add_active_processor(self, PyProcessor proc):
        with nogil:
            check(self.__realm.add_processor(proc.get()))

    def add_active_control_value(self, PyControlValue control_value):
        with nogil:
            check(self.__realm.add_control_value(control_value.release()))

    def add_active_child_realm(self, PyRealm child):
        with nogil:
            check(self.__realm.add_child_realm(child.get()))

    def set_control_value(self, name, value, generation):
        cdef string c_name = name.encode('utf-8')
        cdef float c_float
        cdef uint32_t c_generation = generation
        if isinstance(value, float):
            c_float = value
            with nogil:
                check(self.__realm.set_float_control_value(c_name, c_float, c_generation))
        else:
            raise TypeError(
                "Type %s not supported for control values." % type(value).__name__)

    async def set_plugin_state(self, node, state):
        plugin_host = await self.get_plugin_host()
        await plugin_host.call(
            'SET_PLUGIN_STATE',
            plugin_host_pb2.SetPluginStateRequest(
                realm=self.__name, node_id=node, state=state))

    def set_session_values(self, session_values):
        for session_value in session_values:
            key = session_value.name
            if key.startswith('node/'):
                _, node_id, node_key = key.split('/', 2)
                try:
                    node = self.__graph.find_node(node_id)
                except KeyError:
                    pass
                else:
                    node.set_session_value(node_key, session_value)

    def send_node_message(self, msg):
        node = self.__graph.find_node(msg.node_id)
        assert isinstance(node, graph.ProcessorNode), type(node).__name__
        proc = node.processor

        cdef uint64_t c_processor_id = proc.id
        cdef string c_msg = msg.SerializeToString()
        with nogil:
            check(self.__realm.send_processor_message(c_processor_id, c_msg))

    def update_project_properties(self, properties: audioproc.ProjectProperties):
        if properties.HasField('bpm'):
            self.__bpm = properties.bpm

        if properties.HasField('duration'):
            self.__duration = audioproc.MusicalDuration.from_proto(properties.duration)

        self.update_spec()

    def get_active_program(self):
        cdef StatusOr[Program*] stor_program = self.__realm.get_active_program()
        check(stor_program)
        if stor_program.result() == NULL:
            return None
        cdef PyProgram program = PyProgram()
        program.set(stor_program.result())
        return program

    def process_block(self, PyProgram program):
        with nogil:
            check(self.__realm.process_block(program.get()))

    def run_maintenance(self):
        with nogil:
            check(self.__realm.run_maintenance())

    @staticmethod
    cdef void __notification_callback(
        void* c_self, const string& notification_serialized) with gil:
        cdef PyRealm self = <object><PyObject*>c_self

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

