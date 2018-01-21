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

from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore
from libc cimport stdlib
from libc.string cimport memmove
from libcpp.memory cimport unique_ptr

import asyncio
import enum
import logging
import math
import os
import random
import sys
import threading
import time
import cProfile

from noisicaa import core
from noisicaa import rwlock
from noisicaa.bindings import lv2
from noisicaa.core.status cimport *
from noisicaa.audioproc.public import musical_time
from noisicaa.audioproc.public import player_state_pb2
from .vm cimport *
from .host_data cimport *
from .spec cimport *
from .block_context cimport *
from .buffers cimport *
from .control_value cimport *
from .backend cimport *
from .message_queue cimport *
from .processor cimport *
from .player cimport *
from .. import node
from .. import ports
from . import graph
from . import compiler

logger = logging.getLogger(__name__)


class GraphError(Exception):
    pass


cdef class PipelineVM(object):
    cdef unique_ptr[VM] __vm_ptr
    cdef VM* __vm
    cdef unique_ptr[Backend] __backend_ptr
    cdef Backend* __backend
    cdef unique_ptr[Player] __player_ptr
    cdef Player* __player

    cdef readonly object listeners
    cdef PyHostData __host_data
    cdef object __event_loop
    cdef object __sample_rate
    cdef object __block_size
    cdef object __shm
    cdef object __profile_path
    cdef object __vm_thread
    cdef object __vm_started
    cdef object __vm_exit
    cdef object __vm_lock
    cdef object __maintenance_task
    cdef object __bpm
    cdef object __duration
    cdef object __graph
    cdef readonly object notification_listener
    cdef object __backend_ready
    cdef object __backend_released

    def __init__(
            self, *,
            host_data, event_loop,
            sample_rate=44100, block_size=128, shm=None, profile_path=None, enable_player=False):
        self.listeners = core.CallbackRegistry()

        self.__host_data = host_data
        self.__event_loop = event_loop
        self.__sample_rate = sample_rate
        self.__block_size = block_size
        self.__shm = shm
        self.__profile_path = profile_path

        self.__vm = NULL
        self.__backend = NULL
        if enable_player:
            logger.info("Enabling player...")
            self.__player_ptr.reset(
                new Player(self.__host_data.ptr(), self.player_state_callback, <PyObject*>self))
            self.__player = self.__player_ptr.get()
        else:
            logger.info("Player disabled.")
            self.__player = NULL

        self.__backend_ready = threading.Event()
        self.__backend_released = threading.Event()

        self.__vm_thread = None
        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = rwlock.RWLock()

        self.__maintenance_task = None

        self.__graph = graph.PipelineGraph()
        self.__bpm = 120
        self.__duration = musical_time.PyMusicalDuration(2, 1)

        self.notification_listener = core.CallbackRegistry()

    def reader_lock(self):
        return self.__vm_lock.reader_lock

    def writer_lock(self):
        return self.__vm_lock.writer_lock

    def dump(self):
        # TODO: reimplement
        pass

    def setup(self, *, start_thread=True):
        if self.__player != NULL:
            check(self.__player.setup())

        self.__vm_ptr.reset(new VM(self.__host_data.ptr(), self.__player))
        self.__vm = self.__vm_ptr.get()
        check(self.__vm.setup())
        self.__vm.set_block_size(self.__block_size)

        self.__vm_started = threading.Event()
        self.__vm_exit = threading.Event()
        if start_thread:
            self.__vm_thread = threading.Thread(target=self.vm_main)
            self.__vm_thread.start()
            logger.info("Starting VM thread (%s)...", self.__vm_thread.ident)
            self.__vm_started.wait()

            logger.info("Starting maintenance task...")
            self.__maintenance_task = self.__event_loop.create_task(self.__maintenance_task_main())

        logger.info("VM up and running.")

    def cleanup(self):
        if self.__backend != NULL:
            logger.info("Stopping backend...")
            self.__backend.stop()

        if self.__maintenance_task is not None:
            logger.info("Shutting down maintenance task...")
            self.__maintenance_task.cancel()
            self.__maintenance_task = None

        if self.__vm_thread is not None:  # pragma: no branch
            logger.info("Shutting down VM thread...")
            self.__vm_exit.set()
            self.__vm_thread.join()
            self.__vm_thread = None
            logger.info("VM thread stopped.")

        if self.__backend != NULL:
            self.__backend.cleanup()
            self.__backend = NULL
            self.__backend_ptr.reset()

        self.__vm_started = None
        self.__vm_exit = None

        if self.__vm != NULL:
            self.__vm.cleanup()
        self.__vm_ptr.reset()

        if self.__player != NULL:
            with nogil:
                self.__player.cleanup()

    def set_spec(self, PySpec spec):
        self.__vm.set_spec(spec.release())

    def update_spec(self):
        spec = compiler.compile_graph(
            graph=self.__graph)
        spec.bpm = self.__bpm
        spec.duration = self.__duration
        self.set_spec(spec)

    def get_buffer_bytes(self, name):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)
        cdef Buffer* buf = self.__vm.get_buffer(name)
        assert buf != NULL
        return bytes(buf.data()[:buf.size()])

    def set_buffer_bytes(self, name, data):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)
        cdef Buffer* buf = self.__vm.get_buffer(name)
        assert buf != NULL
        assert len(data) == buf.size()
        memmove(buf.data(), <char*>data, buf.size())

    def set_backend(self, name, **parameters):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        if self.__backend_ptr.get() != NULL:
            self.__backend.release()
            self.__backend_released.wait()
            self.__backend_released.clear()

            self.__backend.cleanup()
            self.__backend_ptr.reset()
            self.__backend = NULL

        cdef PyBackendSettings settings = PyBackendSettings(**parameters)
        cdef StatusOr[Backend*] backend = Backend.create(name, settings.get())
        check(backend)
        cdef unique_ptr[Backend] backend_ptr
        backend_ptr.reset(backend.result())

        check(backend_ptr.get().setup(self.__vm))

        self.__backend_ptr.reset(backend_ptr.release())
        self.__backend = self.__backend_ptr.get()
        self.__backend_ready.set()

    def set_backend_parameters(self, block_size=None):
        if self.__backend != NULL:
            if block_size != None:
                check(self.__backend.set_block_size(block_size))

    def send_message(self, msg):
        if self.__backend != NULL:
            check(self.__backend.send_message(msg))

    @property
    def nodes(self):
        return self.__graph.nodes

    def find_node(self, node_id):
        return self.__graph.find_node(node_id)

    def add_node(self, node):
        if node.pipeline is not None:
            raise GraphError("Node has already been added to a pipeline")
        node.pipeline = self
        self.__graph.add_node(node)

    def remove_node(self, node):
        if node.pipeline is not self:
            raise GraphError("Node has not been added to this pipeline")
        node.pipeline = None
        self.__graph.remove_node(node)

    def setup_node(self, node):
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
        node.setup()
        # if self._shm_data is not None:
        #     self._shm_data[512] = 0

        cdef PyProcessor processor = node.get_processor()
        if processor is not None:
            self.__vm.add_processor(processor.release())

        cdef PyControlValue cv
        for cv in node.control_values:
            self.__vm.add_control_value(cv.release());

    def set_control_value(self, name, value):
        if isinstance(value, float):
            check(self.__vm.set_float_control_value(name.encode('utf-8'), value))
        else:
            raise TypeError(
                "Type %s not supported for control values." % type(value).__name__)

    def send_node_message(self, node_id, msg):
        n = self.__graph.find_node(node_id)
        assert isinstance(n, node.ProcessorNode), type(n).__name__
        proc = n.get_processor()
        assert proc is not None

        check(self.__vm.send_processor_message(proc.id, msg.SerializeToString()))

    def update_player_state(self, state):
        assert self.__player != NULL
        self.__player.update_state(state.SerializeToString())

    def update_project_properties(self, *, bpm=None, duration=None):
        if bpm is not None:
            self.__bpm = bpm

        if duration is not None:
            self.__duration = duration

        self.update_spec()

    @staticmethod
    cdef void player_state_callback(void* c_self, const string& state_serialized) with gil:
        cdef PipelineVM self = <object><PyObject*>c_self

        # Have to stash away any active exception, because otherwise exception handling
        # might get confused.
        # See https://github.com/cython/cython/issues/1877
        cdef PyObject* exc_type
        cdef PyObject* exc_value
        cdef PyObject* exc_trackback
        PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)
        try:
            state_pb = player_state_pb2.PlayerState()
            state_pb.ParseFromString(state_serialized)
            self.listeners.call('player_state', state_pb)

        finally:
            PyErr_Restore(exc_type, exc_value, exc_trackback)

    def vm_main(self):
        profiler = None
        try:
            logger.info("Starting VM...")

            self.__vm_started.set()

            if self.__profile_path:
                profiler = cProfile.Profile()
                profiler.enable()
            try:
                self.vm_loop()
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
            logger.info("VM finished.")

    def vm_loop(self):
        cdef Backend* backend = NULL
        cdef MessageQueue* out_messages
        cdef Message* msg

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.sample_pos = 0
        ctxt.block_size = self.__block_size

        while True:
            if self.__vm_exit.is_set():
                logger.info("Exiting VM mainloop.")
                break

            if backend == NULL:
                if self.__backend_ready.wait(0.1):
                    self.__backend_ready.clear()
                    assert self.__backend != NULL
                    backend = self.__backend
                else:
                    continue

            elif backend.released():
                backend = NULL
                self.__backend_released.set()
                continue

            if backend.stopped():
                logger.info("Backend stopped, exiting VM mainloop.")
                break

            if len(ctxt.perf) > 0:
                self.listeners.call('perf_data', ctxt.perf.serialize())
            ctxt.perf.reset()

            with nogil:
                check(self.__vm.process_block(backend, ctxt.get()))

            out_messages = ctxt.get().out_messages.get()
            msg = out_messages.first()
            while not out_messages.is_end(msg):
                if msg.type == MessageType.SOUND_FILE_COMPLETE:
                    node_id = bytes((<SoundFileCompleteMessage*>msg).node_id).decode('utf-8')
                    self.notification_listener.call(node_id, msg.type)

                else:
                    logger.info("out message %d", msg.type)
                msg = out_messages.next(msg)
            out_messages.clear()

            ctxt.sample_pos += ctxt.block_size

    def process_block(self, PyBlockContext ctxt):
        check(self.__vm.process_block(self.__backend, ctxt.get()))

    async def __maintenance_task_main(self):
        while True:
            logger.debug("Running maintenance task...")
            with nogil:
                check(self.__vm.run_maintenance())
            await asyncio.sleep(0.2, self.__event_loop)
