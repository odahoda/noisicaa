#!/usr/bin/python3

import logging
import struct
import threading
import unittest

from noisicaa import node_db
from noisicaa import audioproc
from .. import backend
from .. import resample
from .. import nodes
from . import buffers
from . import engine
from . import spec

logger = logging.getLogger(__name__)


class TestBackend(backend.Backend):
    def __init__(self, step_mode=False):
        super().__init__()

        self.written_frames = []
        self.step_mode = step_mode
        self.start_step = threading.Event()
        self.step_done = threading.Event()

    def begin_frame(self, ctxt):
        logger.info("Backend.begin_frame()")
        if self.step_mode:
            self.start_step.wait()
            self.start_step.clear()

    def end_frame(self):
        logger.info("Backend.end_frame()")
        if self.step_mode:
            self.step_done.set()

    def output(self, channel, samples):
        logger.info("Backend received frame.")
        self.written_frames.append([channel, samples])

    def stop(self):
        if self.step_mode:
            self.start_step.set()
        super().stop()

    def next_step(self):
        assert self.step_mode
        self.start_step.set()
        self.step_done.wait()
        self.step_done.clear()


class PipelineVMTest(unittest.TestCase):

    def test_get_buffer_bytes(self):
        vm = engine.PipelineVM()

        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm.setup_spec(vm_spec)

        vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))
        self.assertEqual(
            vm.get_buffer_bytes(0),
            struct.pack('=ffff', 1, 2, 3, 4))

    def test_vm_thread(self):
        vm = engine.PipelineVM()
        try:
            vm.setup()
            be = TestBackend(step_mode=True)
            vm.set_backend(be)

            # run once w/o a spec
            be.next_step()

            # run with a spec
            vm_spec = spec.PipelineVMSpec()
            vm_spec.buffers.append(buffers.Float())
            vm_spec.opcodes.append(spec.OpCode('SET_FLOAT', buf_idx=0, value=12))
            vm.set_spec(vm_spec)
            be.next_step()

            # replace spec
            vm_spec = spec.PipelineVMSpec()
            vm_spec.buffers.append(buffers.Float())
            vm_spec.opcodes.append(spec.OpCode('SET_FLOAT', buf_idx=0, value=14))
            vm.set_spec(vm_spec)
            be.next_step()

            # run once w/o a spec
            vm.set_spec(None)
            be.next_step()

        finally:
            vm.cleanup()

    def test_run_vm(self):
        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.Float())
        vm_spec.buffers.append(buffers.FloatArray(256))
        vm_spec.buffers.append(buffers.FloatArray(256))
        vm_spec.opcodes.append(spec.OpCode('SET_FLOAT', buf_idx=0, value=12))
        vm_spec.opcodes.append(spec.OpCode('COPY_BUFFER', src_idx=1, dest_idx=2))

        vm = engine.PipelineVM()
        vm.setup_spec(vm_spec)

        ctxt = audioproc.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 128

        vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    def test_OUTPUT(self):
        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm_spec.opcodes.append(spec.OpCode('OUTPUT', buf_idx=0, channel='center'))

        be = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(vm_spec)
        vm.setup_backend(be)

        vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))

        ctxt = audioproc.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(len(be.written_frames), 1)
        channel, samples = be.written_frames[0]
        self.assertEqual(channel, 'center')
        self.assertEqual(samples, struct.pack('=ffff', 1, 2, 3, 4))

    def test_NOISE(self):
        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm_spec.opcodes.append(spec.OpCode('NOISE', buf_idx=0))

        be = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(vm_spec)
        vm.setup_backend(be)

        ctxt = audioproc.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

        for sample in struct.unpack('=ffff', vm.get_buffer_bytes(0)):
            self.assertGreaterEqual(sample, -1.0)
            self.assertLessEqual(sample, 1.0)

    def test_MUL(self):
        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm_spec.opcodes.append(spec.OpCode('MUL', buf_idx=0, factor=2))

        be = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(vm_spec)
        vm.setup_backend(be)

        vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))

        ctxt = audioproc.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(
            vm.get_buffer_bytes(0),
            struct.pack('=ffff', 2, 4, 6, 8))

    def test_MIX(self):
        vm_spec = spec.PipelineVMSpec()
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm_spec.buffers.append(buffers.FloatArray(4))
        vm_spec.opcodes.append(spec.OpCode('MIX', src_idx=1, dest_idx=0))

        be = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(vm_spec)
        vm.setup_backend(be)

        vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))
        vm.set_buffer_bytes(1, struct.pack('=ffff', 2, 2, 4, 4))

        ctxt = audioproc.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(
            struct.unpack('=ffff', vm.get_buffer_bytes(0)),
            (3.0, 4.0, 7.0, 8.0))

    def test_CALL(self):
        vm = engine.PipelineVM()

        description = node_db.NodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ],
            parameters=[
                node_db.InternalParameterDescription(
                    name='uri', value='http://lv2plug.in/plugins/eg-amp'),
                node_db.FloatParameterDescription(
                    name='gain',
                    display_name='Gain',
                    default=0.0,
                    min=-90.0,
                    max=24.0),
            ])

        node = nodes.LV2(description=description, id='node')
        node.setup()
        try:
            node.set_param(gain=-20.0)

            vm.add_node(node)

            vm_spec = spec.PipelineVMSpec()
            vm_spec.buffers.append(buffers.FloatArray(4))
            vm_spec.buffers.append(buffers.FloatArray(4))
            vm_spec.nodes.append('node')
            vm_spec.opcodes.append(spec.OpCode(
                'CONNECT_PORT', node_idx=0, port_name='in', buf_idx=0))
            vm_spec.opcodes.append(spec.OpCode(
                'CONNECT_PORT', node_idx=0, port_name='out', buf_idx=1))
            vm_spec.opcodes.append(spec.OpCode(
                'CALL', node_idx=0))
            vm.setup_spec(vm_spec)

            be = TestBackend()
            vm.setup_backend(be)

            vm.set_buffer_bytes(0, struct.pack('=ffff', 20, 40, 60, 80))

            ctxt = audioproc.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 4

            vm.run_vm(vm_spec, ctxt, engine.RunAt.INIT)
            vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

            self.assertEqual(
                struct.unpack('=ffff', vm.get_buffer_bytes(1)),
                (2.0, 4.0, 6.0, 8.0))

        finally:
            node.cleanup()

    # def test_play(self):
    #     vm = engine.PipelineVM()
    #     try:
    #         vm.setup()
    #         vm.set_backend(backend.PyAudioBackend())

    #         vm_spec = spec.PipelineVMSpec()
    #         vm_spec.buffers.append(buffers.FloatArray(128))
    #         vm_spec.buffers.append(buffers.FloatArray(128))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'SINE', buf_idx=0, freq=440))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'MUL', buf_idx=0, factor=0.8))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'NOISE', buf_idx=1))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'MUL', buf_idx=1, factor=0.2))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'MIX', src_idx=1, dest_idx=0))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'OUTPUT_STEREO', buf_idx_l=0, buf_idx_r=0))
    #         vm.set_spec(vm_spec)

    #         import time
    #         time.sleep(2.0)

    #     finally:
    #         vm.cleanup()


if __name__ == '__main__':
    unittest.main()
