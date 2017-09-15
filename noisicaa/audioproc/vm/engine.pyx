#!/usr/bin/python3

from libc cimport stdlib
from libc.string cimport memmove
from libcpp.memory cimport unique_ptr

import enum
import logging
import math
import os
import random
import sys
import threading
import time
import cProfile

from noisicore.status cimport *
from noisicore.vm cimport *
from noisicore.host_data cimport *
from noisicore.spec cimport *
from noisicore.block_context cimport *
from noisicore.buffers cimport *
from noisicore.backend cimport *

import noisicore
from noisicaa import core
from noisicaa import rwlock
from noisicaa import audioproc
from noisicaa.bindings import lv2
from .. import node
from . import graph
from . import compiler

logger = logging.getLogger(__name__)


class GraphError(Exception):
    pass


cdef class PipelineVM(object):
    cdef unique_ptr[VM] __vm_ptr
    cdef VM* __vm

    cdef readonly object listeners
    cdef PyHostData __host_data
    cdef object __sample_rate
    cdef object __block_size
    cdef object __shm
    cdef object __profile_path
    cdef object __vm_thread
    cdef object __vm_started
    cdef object __vm_exit
    cdef object __vm_lock
    cdef object __graph
    cdef object __parameters
    cdef object __notifications
    cdef readonly object notification_listener

    def __init__(
            self, *,
            host_data,
            sample_rate=44100, block_size=128, shm=None, profile_path=None):
        self.listeners = core.CallbackRegistry()

        self.__host_data = host_data
        self.__sample_rate = sample_rate
        self.__block_size = block_size
        self.__shm = shm
        self.__profile_path = profile_path

        self.__vm_thread = None
        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = rwlock.RWLock()

        self.__graph = graph.PipelineGraph()
        self.__parameters = {}

        self.__notifications = []
        self.notification_listener = core.CallbackRegistry()

    def reader_lock(self):
        return self.__vm_lock.reader_lock

    def writer_lock(self):
        return self.__vm_lock.writer_lock

    def dump(self):
        # TODO: reimplement
        pass

    def setup(self, *, start_thread=True):
        self.__vm_ptr.reset(new VM(self.__host_data.ptr()))
        self.__vm = self.__vm_ptr.get()
        check(self.__vm.setup())
        self.__vm.set_block_size(self.__block_size)

        self.__vm_started = threading.Event()
        self.__vm_exit = threading.Event()
        if start_thread:
            self.__vm_thread = threading.Thread(target=self.vm_main)
            self.__vm_thread.start()
            self.__vm_started.wait()
        logger.info("VM up and running.")

    def cleanup(self):
        # if self.__backend is not None:
        #     logger.info("Stopping backend...")
        #     self.__backend.stop()
        #     logger.info("Backend stopped...")

        if self.__vm_thread is not None:  # pragma: no branch
            logger.info("Shutting down VM thread...")
            self.__vm_exit.set()
            self.__vm_thread.join()
            self.__vm_thread = None
            logger.info("VM thread stopped.")

        self.__vm_started = None
        self.__vm_exit = None

        if self.__vm != NULL:
            self.__vm.cleanup()
        self.__vm_ptr.reset()

    def set_spec(self, PySpec spec):
        self.__vm.set_spec(spec.release())

    def update_spec(self):
        spec = compiler.compile_graph(
            graph=self.__graph)
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

        cdef PyBackendSettings settings = PyBackendSettings(**parameters)
        cdef StatusOr[Backend*] backend = Backend.create(name, settings.get())
        check(backend)
        check(self.__vm.set_backend(backend.result()))

    def set_backend_parameters(self, parameters):
        logger.info(
            "%s backend: set_parameters(%s)",
            type(self.__backend).__name__, parameters)
        with self.writer_lock():
            if self.__backend is not None:
                self.__backend.set_parameters(**parameters)

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

        logger.info("setup complete")
        cdef PyProcessor processor = node.get_processor()
        if processor is not None:
            logger.info("adding processor")
            self.__vm.add_processor(processor.release())
            logger.info("done")

    def set_parameter(self, name, value):
        self.__parameters[name] = value

    def add_notification(self, node_id, notification):
        self.__notifications.append((node_id, notification))

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
        cdef BlockContext ctxt
        #ctxt.perf = core.PerfStats()
        ctxt.sample_pos = 0
        ctxt.block_size = self.__block_size

        while True:
            if self.__vm_exit.is_set():
                logger.info("Exiting VM mainloop.")
                break

            with nogil:
                check(self.__vm.process_block(&ctxt))

            # backend = self.__backend
            # if backend is None:
            #     time.sleep(0.1)
            #     continue

            # self.listeners.call('perf_data', ctxt.perf.serialize())

            # ctxt.perf = core.PerfStats()

            # backend.begin_frame(ctxt)

            # try:
            #     if backend.stopped:
            #         break

            #     if ctxt.duration != self.__frame_size:
            #         logger.info("frame_size=%d", ctxt.duration)
            #         with self.writer_lock():
            #             self.__frame_size = ctxt.duration
            #             self.update_spec()

            #     with self.reader_lock():
            #         if self.__spec is not None:
            #             # if not self.__spec_initialized:
            #             #     self.run_vm(self.__spec, ctxt, RunAt.INIT)
            #             #     self.__spec_initialized = True
            #             # self.run_vm(self.__spec, ctxt, RunAt.PERFORMANCE)
            #             pass
            #         else:
            #             time.sleep(0.05)

            # finally:
            #     notifications = self.__notifications
            #     self.__notifications = []

            #     with ctxt.perf.track('send_notifications'):
            #         for node_id, notification in notifications:
            #             self.notification_listener.call(node_id, notification)

            #     backend.end_frame()

            ctxt.sample_pos += ctxt.block_size

    def process_block(self, PyBlockContext ctxt):
        check(self.__vm.process_block(ctxt.ptr()))
