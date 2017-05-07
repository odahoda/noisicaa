#!/usr/bin/python3

import enum
import logging
import math
import os
import random
import struct
import sys
import threading
import time

import toposort

from noisicaa import core
from noisicaa import rwlock
from .. import data
from .. import resample
from .. import node
from . import graph
from . import spec
from . import compiler

logger = logging.getLogger(__name__)


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
            sample_rate=44100, frame_size=128, shm=None):
        self.listeners = core.CallbackRegistry()

        self.__sample_rate = sample_rate
        self.__frame_size = frame_size
        self.__shm = shm

        self.__vm_thread = None
        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = rwlock.RWLock()

        self.__backend = None
        self.__spec = None
        self.__spec_initialized = None
        self.__opcode_states = None
        self.__buffer = None
        self.__buffer_map = None
        self.__graph = graph.PipelineGraph()

        self.__notifications = []
        self.notification_listener = core.CallbackRegistry()

    def reader_lock(self):
        return self.__vm_lock.reader_lock

    def writer_lock(self):
        return self.__vm_lock.writer_lock

    def setup(self):
        self.__vm_started = threading.Event()
        self.__vm_exit = threading.Event()
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

    def setup_spec(self, s):
        self.allocate_buffer(s.buffer_size)
        self.__opcode_states = [{} for _ in s.opcodes]
        self.__spec = s
        self.__spec_initialized = False

    def cleanup_spec(self):
        self.__buffer = None
        self.__opcode_states = None
        self.__spec = None
        self.__spec_initialized = None

    def set_spec(self, s):
        logger.info("spec=%s", s.dump() if s is not None else None)
        with self.writer_lock():
            self.cleanup_spec()

            if s is not None:
                self.setup_spec(s)

    def update_spec(self):
        with self.writer_lock():
            s = compiler.compile_graph(graph=self.__graph, frame_size=self.__frame_size)
            self.set_spec(s)

    def allocate_buffer(self, size):
        self.__buffer = bytearray(size)

    def get_buffer_bytes(self, offset, length):
        return bytes(self.__buffer[offset:offset+length])

    def set_buffer_bytes(self, offset, data):
        self.__buffer[offset:offset+len(data)] = data

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

    def set_frame_size(self, frame_size):
        with self.writer_lock():
            self.__frame_size = frame_size
            # TODO: recompute buffers

    @property
    def nodes(self):
        return self.__graph.nodes

    def find_node(self, node_id):
        return self.__graph.find_node(node_id)

    def add_node(self, node):
        if node.pipeline is not None:
            raise Error("Node has already been added to a pipeline")
        node.pipeline = self
        self.__graph.add_node(node)

    def remove_node(self, node):
        if node.pipeline is not self:
            raise Error("Node has not been added to this pipeline")
        node.pipeline = None
        self.__graph.remove_node(node)

    async def setup_node(self, node):
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

    def add_notification(self, node_id, notification):
        self.__notifications.append((node_id, notification))

    def vm_main(self):
        try:
            logger.info("Starting VM...")

            ctxt = data.FrameContext()
            ctxt.perf = core.PerfStats()
            ctxt.sample_pos = 0
            ctxt.duration = self.__frame_size

            self.__vm_started.set()

            while True:
                if self.__vm_exit.is_set():
                    logger.info("Exiting VM mainloop.")
                    break

                # TODO: remove traces of in/out_frame
                ctxt.in_frame = None
                ctxt.out_frame = None

                backend = self.__backend
                if backend is None:
                    time.sleep(0.1)
                    continue

                self.listeners.call(
                    'perf_data', ctxt.perf.get_spans())

                ctxt.perf = core.PerfStats()

                with ctxt.perf.track('backend_begin_frame'):
                    backend.begin_frame(ctxt)

                try:
                    if backend.stopped:
                        break

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

                    with ctxt.perf.track('backend_end_frame'):
                        backend.end_frame(ctxt)

                ctxt.sample_pos += ctxt.duration
                ctxt.duration = self.__frame_size

        except:  # pragma: no coverage  # pylint: disable=bare-except
            sys.stdout.flush()
            sys.excepthook(*sys.exc_info())
            sys.stderr.flush()
            os._exit(1)  # pylint: disable=protected-access

        finally:
            logger.info("VM finished.")

    def run_vm(self, s, ctxt, run_at):
        for opcode, state in zip(s.opcodes, self.__opcode_states):
            opmethod = getattr(self, 'op_' + opcode.op)
            if opmethod.run_at == run_at:
                logger.debug("Executing opcode %s", opcode)
                opmethod(ctxt, state, **opcode.args)

    @at_performance
    def op_COPY_BUFFER(
            self, ctxt, state, *, src_offset, dest_offset, length):
        assert 0 <= src_offset <= len(self.__buffer) - length
        assert 0 <= dest_offset <= len(self.__buffer) - length

        self.__buffer[dest_offset:dest_offset+length] = self.__buffer[src_offset:src_offset+length]

    @at_performance
    def op_CLEAR_BUFFER(
            self, ctxt, state, *, offset, length):
        assert 0 <= offset <= len(self.__buffer) - length

        for i in range(offset, offset + length):
            self.__buffer[i] = 0

    @at_performance
    def op_SET_FLOAT(self, ctxt, state, *, offset, value):
        assert 0 <= offset <= len(self.__buffer) - 4

        struct.pack_into('=f', self.__buffer, offset, value)

    @at_performance
    def op_OUTPUT_STEREO(
            self, ctxt, state, *, offset_l, offset_r, num_samples):
        assert 0 <= offset_l <= len(self.__buffer) - 4 * num_samples
        assert 0 <= offset_r <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        self.__backend.output(
            resample.AV_CH_LAYOUT_STEREO,
            num_samples,
            [bytes(self.__buffer[offset_l:offset_l+4*num_samples]),
             bytes(self.__buffer[offset_r:offset_r+4*num_samples])])

    @at_performance
    def op_NOISE(self, ctxt, state, *, offset, num_samples):
        assert 0 <= offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(offset, offset + 4 * num_samples, 4):
            self.__buffer[i:i+4] = struct.pack(
                '=f', 2 * random.random() - 1.0)

    @at_performance
    def op_SINE(self, ctxt, state, *, offset, num_samples, freq):
        assert 0 <= offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        p = state.get('p', 0.0)
        for i in range(offset, offset + 4 * num_samples, 4):
            self.__buffer[i:i+4] = struct.pack(
                '=f', math.sin(p))
            p += 2 * math.pi * freq / self.__sample_rate
            if p > 2 * math.pi:
                p -= 2 * math.pi
        state['p'] = p

    @at_performance
    def op_MUL(self, ctxt, state, *, offset, num_samples, factor):
        assert 0 <= offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(offset, offset + 4 * num_samples, 4):
            self.__buffer[i:i+4] = struct.pack(
                '=f', factor * struct.unpack(
                    '=f', self.__buffer[i:i+4])[0])

    @at_performance
    def op_MIX(
            self, ctxt, state, *,
            src_offset, dest_offset, num_samples):
        assert 0 <= src_offset <= len(self.__buffer) - 4 * num_samples
        assert 0 <= dest_offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(0, 4 * num_samples, 4):
            src_val = struct.unpack(
                '=f', self.__buffer[src_offset+i:src_offset+i+4])[0]
            dest_val = struct.unpack(
                '=f', self.__buffer[dest_offset+i:dest_offset+i+4])[0]
            self.__buffer[dest_offset+i:dest_offset+i+4] = struct.pack(
                '=f', dest_val + src_val)

    @at_init
    def op_CONNECT_PORT(
            self, ctxt, state, *, node_idx, port_name, offset):
        node_id = self.__spec.nodes[node_idx]
        node = self.__graph.find_node(node_id)
        node.connect_port(
            port_name, self.__buffer, offset)

    @at_performance
    def op_CALL(self, ctxt, state, *, node_idx):
        node_id = self.__spec.nodes[node_idx]
        node = self.__graph.find_node(node_id)
        node.run(ctxt)
