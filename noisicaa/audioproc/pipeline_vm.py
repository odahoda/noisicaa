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
from . import data
from . import resample
from . import node

logger = logging.getLogger(__name__)


class OpCode(object):
    def __init__(self, op, **args):
        self.op = op
        self.args = args

    def __repr__(self):
        return '%s(%s)' % (
            self.op,
            ', '.join(
                '%s=%r' % (k, v) for k, v in sorted(self.args.items())))


class BufferType(enum.Enum):
    FLOATS = 1


class BufferRef(object):
    def __init__(self, id, offset, length, type):
        self.id = id
        self.offset = offset
        self.length = length
        self.type = type

    def __repr__(self):
        return '%s (%s): %d@%d' % (
            self.id, self.type.name, self.length, self.offset)


class FloatBufferRef(BufferRef):
    def __init__(self, id, offset, count):
        super().__init__(id, offset, 4 * count, BufferType.FLOATS)


class PipelineVMSpec(object):
    def __init__(self):
        self.opcodes = []
        self.buffers = []
        self.nodes = []


class PipelineGraph(object):
    def __init__(self):
        self.__nodes = {}

    @property
    def nodes(self):
        return set(self.__nodes.values())

    def find_node(self, node_id):
        return self.__nodes[node_id]

    def add_node(self, node):
        self.__nodes[node.id] = node

    def remove_node(self, node):
        del self.__nodes[node.id]


def compile_spec(graph, frame_size):
    spec = PipelineVMSpec()

    sorted_nodes = toposort.toposort_flatten(
        {n: set(n.parent_nodes) for n in graph.nodes},
        sort=False)

    buffer_offset = 0
    buffer_map = {}
    for n in sorted_nodes:
        node_idx = len(spec.nodes)
        port_map = []
        for port_name, port in n.outputs.items():
            buffer_id = '%s:%s' % (n.id, port_name)
            port_map.append((port_name, buffer_id))
            buffer_ref = FloatBufferRef(
                buffer_id, buffer_offset, frame_size)
            buffer_map[buffer_id] = buffer_ref
            spec.buffers.append(buffer_ref)
            buffer_offset += buffer_ref.length

        for port_name, port in n.inputs.items():
            buffer_id = '%s:%s' % (n.id, port_name)
            port_map.append((port_name, buffer_id))
            buffer_ref = FloatBufferRef(
                buffer_id, buffer_offset, frame_size)
            buffer_map[buffer_id] = buffer_ref
            spec.buffers.append(buffer_ref)
            buffer_offset += buffer_ref.length

        spec.nodes.append([n.id, port_map])

        for port_name, port in n.inputs.items():
            buffer_id = '%s:%s' % (n.id, port_name)
            buffer_ref = buffer_map[buffer_id]

            first = True
            for upstream_port in port.inputs:
                upstream_buffer_id = '%s:%s' % (
                    upstream_port.owner.id, upstream_port.name)
                upstream_buffer_ref = buffer_map[upstream_buffer_id]

                assert buffer_ref.length == upstream_buffer_ref.length

                if first:
                    spec.opcodes.append(OpCode(
                        'COPY_BUFFER',
                        src_offset=upstream_buffer_ref.offset,
                        dest_offset=buffer_ref.offset,
                        length=buffer_ref.length))
                    first = False
                else:
                    spec.opcodes.append(OpCode(
                        'MIX',
                        src_offset=upstream_buffer_ref.offset,
                        dest_offset=buffer_ref.offset,
                        num_samples=frame_size,
                        factor=1.0))

            if first:
                spec.opcodes.append(OpCode(
                    'CLEAR_BUFFER',
                    offset=buffer_ref.offset,
                    length=buffer_ref.length))

        if isinstance(n, node.CustomNode):
            spec.opcodes.append(OpCode('CALL', node_idx=node_idx))
        elif isinstance(n, node.BuiltinNode):
            spec.opcodes.extend(n.opcodes())
        else:
            raise TypeError(type(n))

    return spec


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
        self.__opcode_states = None
        self.__buffer = None
        self.__buffer_map = None
        self.__graph = PipelineGraph()

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

    def setup_spec(self, spec):
        buffer_size = sum(buf.length for buf in spec.buffers)
        self.allocate_buffer(buffer_size)
        self.__buffer_map = {buf.id: buf for buf in spec.buffers}
        self.__opcode_states = [{} for _ in spec.opcodes]
        for node_id, buffer_spec in spec.nodes:
            node = self.__graph.find_node(node_id)
            for port_name, buffer_id in buffer_spec:
                buffer_ref = self.__buffer_map[buffer_id]
                node.connect_port(
                    port_name, self.__buffer, buffer_ref.offset)
        self.__spec = spec

    def cleanup_spec(self):
        self.__buffer = None
        self.__buffer_map = None
        self.__spec = None

    def set_spec(self, spec):
        logger.info("spec=%s", spec)
        with self.writer_lock():
            self.cleanup_spec()

            if spec is not None:
                self.setup_spec(spec)

    def build_spec(self):
        spec = PipelineVMSpec()

        return spec

    def allocate_buffer(self, size):
        self.__buffer = bytearray(size)

    def get_buffer_bytes(self, buf_id):
        ref = self.__buffer_map[buf_id]
        return bytes(self.__buffer[ref.offset:ref.offset+ref.length])

    def set_buffer_bytes(self, buf_id, data):
        ref = self.__buffer_map[buf_id]
        assert len(data) == ref.length
        self.__buffer[ref.offset:ref.offset+ref.length] = data

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
                        spec = self.__spec
                        if spec is not None:
                            self.run_vm(spec, ctxt)
                        else:
                            time.sleep(0.05)

                finally:
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

    def run_vm(self, spec, ctxt):
        for opcode, state in zip(spec.opcodes, self.__opcode_states):
            logger.info("Executing opcode %s", opcode)
            opmethod = getattr(self, 'op_' + opcode.op)
            opmethod(ctxt, state, **opcode.args)

    def op_COPY_BUFFER(
            self, ctxt, state, *, src_offset, dest_offset, length):
        assert 0 <= src_offset <= len(self.__buffer) - length
        assert 0 <= dest_offset <= len(self.__buffer) - length

        self.__buffer[dest_offset:dest_offset+length] = self.__buffer[src_offset:src_offset+length]

    def op_CLEAR_BUFFER(
            self, ctxt, state, *, offset, length):
        assert 0 <= offset <= len(self.__buffer) - length

        for i in range(offset, offset + length):
            self.__buffer[i] = 0

    def op_SET_FLOAT(self, ctxt, state, *, offset, value):
        assert 0 <= offset <= len(self.__buffer) - 4

        struct.pack_into('=f', self.__buffer, offset, value)

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

    def op_NOISE(self, ctxt, state, *, offset, num_samples):
        assert 0 <= offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(offset, offset + 4 * num_samples, 4):
            self.__buffer[i:i+4] = struct.pack(
                '=f', 2 * random.random() - 1.0)

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

    def op_MUL(self, ctxt, state, *, offset, num_samples, factor):
        assert 0 <= offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(offset, offset + 4 * num_samples, 4):
            self.__buffer[i:i+4] = struct.pack(
                '=f', factor * struct.unpack(
                    '=f', self.__buffer[i:i+4])[0])

    def op_MIX(
            self, ctxt, state, *,
            src_offset, dest_offset, num_samples, factor):
        assert 0 <= src_offset <= len(self.__buffer) - 4 * num_samples
        assert 0 <= dest_offset <= len(self.__buffer) - 4 * num_samples
        assert num_samples > 0

        for i in range(0, 4 * num_samples, 4):
            src_val = struct.unpack(
                '=f', self.__buffer[src_offset+i:src_offset+i+4])[0]
            dest_val = struct.unpack(
                '=f', self.__buffer[dest_offset+i:dest_offset+i+4])[0]
            self.__buffer[dest_offset+i:dest_offset+i+4] = struct.pack(
                '=f', dest_val + factor * src_val)

    def op_CALL(self, ctxt, state, *, node_idx):
        node_id = self.__spec.nodes[node_idx][0]
        node = self.__graph.find_node(node_id)
        node.run(ctxt)
