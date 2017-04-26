#!/usr/bin/python3

import logging
import struct
import threading
import time
import unittest

import asynctest

from noisicaa import node_db
from .. import backend
from .. import data
from .. import resample
from .. import nodes
from . import engine

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

    def end_frame(self, ctxt):
        logger.info("Backend.end_frame()")
        if self.step_mode:
            self.step_done.set()

    def output(self, layout, num_samples, data):
        logger.info("Backend received frame.")
        self.written_frames.append([layout, num_samples, data])

    def stop(self):
        if self.step_mode:
            self.start_step.set()
        super().stop()

    def next_step(self):
        assert self.step_mode
        self.start_step.set()
        self.step_done.wait()
        self.step_done.clear()


class PipelineVMTest(asynctest.TestCase):

    async def test_get_buffer_bytes(self):
        vm = engine.PipelineVM()

        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('buf', 0, 4))
        vm.setup_spec(spec)

        vm.set_buffer_bytes('buf', struct.pack('=ffff', 1, 2, 3, 4))
        self.assertEqual(
            vm.get_buffer_bytes('buf'),
            struct.pack('=ffff', 1, 2, 3, 4))

    async def test_vm_thread(self):
        vm = engine.PipelineVM()
        try:
            vm.setup()
            backend = TestBackend(step_mode=True)
            vm.set_backend(backend)

            # run once w/o a spec
            backend.next_step()

            # run with a spec
            spec = engine.PipelineVMSpec()
            spec.buffers.append(engine.FloatBufferRef('foo', 0, 1))
            spec.opcodes.append(
                engine.OpCode('SET_FLOAT', offset=0, value=12))
            vm.set_spec(spec)
            backend.next_step()

            # replace spec
            spec = engine.PipelineVMSpec()
            spec.buffers.append(engine.FloatBufferRef('foo', 0, 1))
            spec.opcodes.append(
                engine.OpCode('SET_FLOAT', offset=0, value=14))
            vm.set_spec(spec)
            backend.next_step()

            # run once w/o a spec
            vm.set_spec(None)
            backend.next_step()

        finally:
            vm.cleanup()

    async def test_run_vm(self):
        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('float', 0, 1))
        spec.buffers.append(engine.FloatBufferRef('buf1', 4, 256))
        spec.buffers.append(engine.FloatBufferRef('buf2', 1028, 256))
        spec.opcodes.append(
            engine.OpCode(
                'SET_FLOAT',
                offset=0, value=12))
        spec.opcodes.append(
            engine.OpCode(
                'COPY_BUFFER',
                src_offset=4, dest_offset=1024, length=1024))

        vm = engine.PipelineVM()
        vm.setup_spec(spec)

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 128

        vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

    async def test_OUTPUT_STEREO(self):
        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('bufl', 0, 4))
        spec.buffers.append(engine.FloatBufferRef('bufr', 16, 4))
        spec.opcodes.append(
            engine.OpCode(
                'OUTPUT_STEREO', offset_l=0, offset_r=16, num_samples=4))

        backend = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('bufl', struct.pack('=ffff', 1, 2, 3, 4))
        vm.set_buffer_bytes('bufr', struct.pack('=ffff', 5, 6, 7, 8))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(len(backend.written_frames), 1)
        layout, num_samples, samples = backend.written_frames[0]
        self.assertEqual(layout, resample.AV_CH_LAYOUT_STEREO)
        self.assertEqual(num_samples, 4)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0], struct.pack('=ffff', 1, 2, 3, 4))
        self.assertEqual(samples[1], struct.pack('=ffff', 5, 6, 7, 8))

    async def test_NOISE(self):
        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('buf', 0, 4))
        spec.opcodes.append(
            engine.OpCode(
                'NOISE', offset=0, num_samples=4))

        backend = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

        for sample in struct.unpack('=ffff', vm.get_buffer_bytes('buf')):
            self.assertGreaterEqual(sample, -1.0)
            self.assertLessEqual(sample, 1.0)

    async def test_MUL(self):
        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('buf', 0, 4))
        spec.opcodes.append(
            engine.OpCode(
                'MUL', offset=0, num_samples=4, factor=2))

        backend = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('buf', struct.pack('=ffff', 1, 2, 3, 4))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(
            vm.get_buffer_bytes('buf'),
            struct.pack('=ffff', 2, 4, 6, 8))

    async def test_MIX(self):
        spec = engine.PipelineVMSpec()
        spec.buffers.append(engine.FloatBufferRef('buf1', 0, 4))
        spec.buffers.append(engine.FloatBufferRef('buf2', 16, 4))
        spec.opcodes.append(
            engine.OpCode(
                'MIX', src_offset=16, dest_offset=0, num_samples=4, factor=0.5))

        backend = TestBackend()

        vm = engine.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('buf1', struct.pack('=ffff', 1, 2, 3, 4))
        vm.set_buffer_bytes('buf2', struct.pack('=ffff', 2, 2, 4, 4))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

        self.assertEqual(
            struct.unpack('=ffff', vm.get_buffer_bytes('buf1')),
            (2.0, 3.0, 5.0, 6.0))

    async def test_CALL(self):
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

        node = nodes.LV2(self.loop, description, id='node')
        await node.setup()
        try:
            node.set_param(gain=-20.0)

            vm.add_node(node)

            spec = engine.PipelineVMSpec()
            spec.buffers.append(engine.FloatBufferRef('buf1', 0, 4))
            spec.buffers.append(engine.FloatBufferRef('buf2', 16, 4))
            spec.nodes.append('node')
            spec.opcodes.append(
                engine.OpCode(
                    'CONNECT_PORT',
                    node_idx=0, port_name='in', offset=0))
            spec.opcodes.append(
                engine.OpCode(
                    'CONNECT_PORT',
                    node_idx=0, port_name='out', offset=16))
            spec.opcodes.append(
                engine.OpCode(
                    'CALL', node_idx=0))
            vm.setup_spec(spec)

            backend = TestBackend()
            vm.setup_backend(backend)

            vm.set_buffer_bytes('buf1', struct.pack('=ffff', 20, 40, 60, 80))

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 4

            vm.run_vm(spec, ctxt, engine.RunAt.INIT)
            vm.run_vm(spec, ctxt, engine.RunAt.PERFORMANCE)

            self.assertEqual(
                struct.unpack('=ffff', vm.get_buffer_bytes('buf2')),
                (2.0, 4.0, 6.0, 8.0))

        finally:
            await node.cleanup()


    # async def test_play(self):
    #     vm = engine.PipelineVM()
    #     try:
    #         vm.setup()
    #         vm.set_backend(backend.PyAudioBackend())

    #         spec = engine.PipelineVMSpec()
    #         spec.buffers.append(engine.FloatBufferRef('buf1', 0, 128))
    #         spec.buffers.append(engine.FloatBufferRef('buf2', 512, 128))
    #         spec.opcodes.append(
    #             engine.OpCode(
    #                 'SINE', offset=0, num_samples=128, freq=440))
    #         spec.opcodes.append(
    #             engine.OpCode(
    #                 'MUL', offset=0, num_samples=128, factor=0.8))
    #         spec.opcodes.append(
    #             engine.OpCode(
    #                 'NOISE', offset=512, num_samples=128))
    #         spec.opcodes.append(
    #             engine.OpCode(
    #                 'MIX', src_offset=512, dest_offset=0, num_samples=128, factor=0.2))
    #         spec.opcodes.append(
    #             engine.OpCode(
    #                 'OUTPUT_STEREO', offset_l=0, offset_r=0, num_samples=128))
    #         vm.set_spec(spec)

    #         time.sleep(2.0)

    #     finally:
    #         vm.cleanup()


if __name__ == '__main__':
    unittest.main()
