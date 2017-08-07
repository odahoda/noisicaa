#!/usr/bin/python3

from libc cimport stdlib
from libc cimport string

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
from noisicaa import audioproc
from noisicaa.bindings import lv2
from .. import resample
from . cimport buffers
from . import buffers
from . import graph
from . import compiler

logger = logging.getLogger(__name__)


class GraphError(Exception):
    pass


class RunAt(enum.Enum):
    PERFORMANCE = 1
    INIT = 2


def at_performance(func):
    func.run_at = RunAt.PERFORMANCE
    return func

def at_init(func):
    func.run_at = RunAt.INIT
    return func


class PipelineVM(object):
    def __init__(
            self, *,
            sample_rate=44100, frame_size=128, shm=None, profile_path=None):
        self.listeners = core.CallbackRegistry()

        self.__sample_rate = sample_rate
        self.__frame_size = frame_size
        self.__shm = shm
        self.__profile_path = profile_path

        self.__vm_thread = None
        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = rwlock.RWLock()

        self.__backend = None
        self.__spec = None
        self.__spec_initialized = None
        self.__opcode_states = None
        self.__buffers = None
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
        self.__vm_started = threading.Event()
        self.__vm_exit = threading.Event()
        if start_thread:
            self.__vm_thread = threading.Thread(target=self.vm_main)
            self.__vm_thread.start()
            self.__vm_started.wait()
        logger.info("VM up and running.")

    def cleanup(self):
        if self.__backend is not None:
            logger.info("Stopping backend...")
            self.__backend.stop()
            logger.info("Backend stopped...")

        if self.__vm_thread is not None:  # pragma: no branch
            logger.info("Shutting down VM thread...")
            self.__vm_exit.set()
            self.__vm_thread.join()
            self.__vm_thread = None
            logger.info("VM thread stopped.")

        self.__vm_started = None
        self.__vm_exit = None

        self.cleanup_backend()
        self.cleanup_spec()

    def setup_spec(self, spec):
        self.__buffers = [buffers.Buffer(btype) for btype in spec.buffers]
        self.__opcode_states = [{} for _ in spec.opcodes]
        self.__spec = spec
        self.__spec_initialized = False

    def cleanup_spec(self):
        self.__buffers = None
        self.__opcode_states = None
        self.__spec = None
        self.__spec_initialized = None

    def set_spec(self, spec):
        logger.info("spec=%s", spec.dump() if spec is not None else None)
        with self.writer_lock():
            self.cleanup_spec()

            if spec is not None:
                self.setup_spec(spec)

    def update_spec(self):
        with self.writer_lock():
            spec = compiler.compile_graph(
                graph=self.__graph,
                frame_size=self.__frame_size)
            self.set_spec(spec)

    def get_buffer_bytes(self, buf_idx):
        return self.__buffers[buf_idx].to_bytes()

    def set_buffer_bytes(self, buf_idx, data):
        self.__buffers[buf_idx].set_bytes(data)

    def cleanup_backend(self):
        if self.__backend is not None:
            logger.info(
                "Clean up backend %s", type(self.__backend).__name__)
            self.__backend.cleanup()
            self.__backend = None

    def setup_backend(self, backend):
        logger.info(
            "Set up backend %s", type(backend).__name__)
        backend.setup(self.__sample_rate)
        self.__backend = backend

    def set_backend(self, backend):
        logger.info("backend=%s", type(backend).__name__)
        with self.writer_lock():
            self.cleanup_backend()

            if backend is not None:
                self.setup_backend(backend)

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
        ctxt = audioproc.FrameContext()
        ctxt.perf = core.PerfStats()
        ctxt.sample_pos = 0
        ctxt.duration = -1

        while True:
            if self.__vm_exit.is_set():
                logger.info("Exiting VM mainloop.")
                break

            backend = self.__backend
            if backend is None:
                time.sleep(0.1)
                continue

            self.listeners.call('perf_data', ctxt.perf.serialize())

            ctxt.perf = core.PerfStats()

            backend.begin_frame(ctxt)

            try:
                if backend.stopped:
                    break

                if ctxt.duration != self.__frame_size:
                    logger.info("frame_size=%d", ctxt.duration)
                    with self.writer_lock():
                        self.__frame_size = ctxt.duration
                        self.update_spec()

                with self.reader_lock():
                    if self.__spec is not None:
                        if not self.__spec_initialized:
                            self.run_vm(self.__spec, ctxt, RunAt.INIT)
                            self.__spec_initialized = True
                        self.run_vm(self.__spec, ctxt, RunAt.PERFORMANCE)
                    else:
                        time.sleep(0.05)

            finally:
                notifications = self.__notifications
                self.__notifications = []

                with ctxt.perf.track('send_notifications'):
                    for node_id, notification in notifications:
                        self.notification_listener.call(node_id, notification)

                backend.end_frame()

            ctxt.sample_pos += ctxt.duration

    def run_vm(self, s, ctxt, run_at):
        for opcode, state in zip(s.opcodes, self.__opcode_states):
            opmethod = getattr(self, 'op_' + opcode.op)
            if opmethod.run_at == run_at:
                logger.debug("Executing opcode %s", opcode)
                opmethod(ctxt, state, **opcode.args)

    # Many opcodes don't use the ctxt or state argument.
    # pylint: disable=unused-argument

    @at_performance
    def op_COPY_BUFFER(self, ctxt, state, *, src_idx, dest_idx):
        cdef buffers.Buffer src = self.__buffers[src_idx]
        cdef buffers.Buffer dest = self.__buffers[dest_idx]
        assert len(src.type) == len(dest.type)
        string.memmove(dest.data, src.data, len(dest.type))

    @at_performance
    def op_CLEAR_BUFFER(self, ctxt, state, *, buf_idx):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        buf.clear()

    @at_performance
    def op_SET_FLOAT(self, ctxt, state, *, buf_idx, value):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        assert isinstance(buf.type, buffers.Float), str(buf.type)
        cdef float* data = <float*>buf.data
        data[0] = value

    @at_performance
    def op_OUTPUT(self, ctxt, state, *, buf_idx, channel):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
        assert buf.type.size == ctxt.duration
        self.__backend.output(channel, buf.to_bytes())

    @at_performance
    def op_FETCH_ENTITY(self, ctxt, state, *, entity_id, buf_idx):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        try:
            entity = ctxt.entities[entity_id]
        except KeyError:
            buf.clear()
        else:
            buf.set_bytes(entity.data)

    @at_performance
    def op_FETCH_PARAMETER(self, ctxt, state, *, parameter_idx, buf_idx):
        #parameter_name = self.__parameters[parameter_idx]
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        buf.clear()

    @at_performance
    def op_FETCH_MESSAGES(self, ctxt, state, *, labelset, buf_idx):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]

        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(buf.data, len(buf.type))

        with forge.sequence():
            for msg in ctxt.messages:
                if msg.type != core.MessageType.atom:
                    continue

                matched = all(
                    any(label_b.key == label_a.key and label_b.value == label_a.value
                        for label_b in msg.labelset.labels)
                    for label_a in labelset.labels)

                if not matched:
                    continue

                forge.write_raw_event(0, msg.data, len(msg.data))

        # TODO: clear remainder of buf.

    @at_performance
    def op_NOISE(self, ctxt, state, *, buf_idx):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        assert isinstance(buf.type, buffers.FloatArray), str(buf.type)

        cdef float* view = <float*>buf.data
        for i in range(buf.type.size):
            view[i] = 2 * random.random() - 1.0

    @at_performance
    def op_SINE(self, ctxt, state, *, buf_idx, freq):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
        cdef float* view = <float*>buf.data

        p = state.get('p', 0.0)
        for i in range(buf.type.size):
            view[i] = math.sin(p)
            p += 2 * math.pi * freq / self.__sample_rate
            if p > 2 * math.pi:
                p -= 2 * math.pi
        state['p'] = p

    @at_performance
    def op_MUL(self, ctxt, state, *, buf_idx, factor):
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
        cdef float* view = <float*>buf.data
        for i in range(buf.type.size):
            view[i] *= factor

    @at_performance
    def op_MIX(self, ctxt, state, *, src_idx, dest_idx):
        self.__buffers[dest_idx].mix(self.__buffers[src_idx])

    @at_init
    def op_CONNECT_PORT(self, ctxt, state, *, node_idx, port_name, buf_idx):
        node_id = self.__spec.nodes[node_idx]
        node = self.__graph.find_node(node_id)
        cdef buffers.Buffer buf = self.__buffers[buf_idx]
        node.connect_port(port_name, memoryview(buf))

    @at_performance
    def op_CALL(self, ctxt, state, *, node_idx):
        node_id = self.__spec.nodes[node_idx]
        node = self.__graph.find_node(node_id)
        node.run(ctxt)
