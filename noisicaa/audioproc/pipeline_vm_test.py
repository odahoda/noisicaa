#!/usr/bin/python3

import logging
import struct
import threading
import time
import unittest

import asynctest

from noisicaa import node_db
from . import backend
from . import data
from . import pipeline_vm
from . import resample
from . import nodes

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


class CompileSpecTest(asynctest.TestCase):
    async def test_foo(self):
        graph = pipeline_vm.PipelineGraph()

        node1 = nodes.PassThru(self.loop)
        graph.add_node(node1)

        node2 = nodes.PassThru(self.loop)
        graph.add_node(node2)
        node2.inputs['in'].connect(node1.outputs['out'])

        node3 = nodes.Sink(self.loop)
        graph.add_node(node3)
        node3.inputs['audio_left'].connect(node1.outputs['out'])
        node3.inputs['audio_left'].connect(node2.outputs['out'])
        node3.inputs['audio_right'].connect(node2.outputs['out'])

        spec = pipeline_vm.compile_spec(graph, 1024)

        print("Buffers:\n%s" % '\n'.join(repr(i) for i in spec.buffers))
        print("Nodes:\n%s" % '\n'.join(repr(i) for i in spec.nodes))
        print("Opcodes:\n%s" % '\n'.join(repr(i) for i in spec.opcodes))


class PipelineVMTest(asynctest.TestCase):

    async def test_get_buffer_bytes(self):
        vm = pipeline_vm.PipelineVM()

        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf', 0, 4))
        vm.setup_spec(spec)

        vm.set_buffer_bytes('buf', struct.pack('=ffff', 1, 2, 3, 4))
        self.assertEqual(
            vm.get_buffer_bytes('buf'),
            struct.pack('=ffff', 1, 2, 3, 4))

    async def test_vm_thread(self):
        vm = pipeline_vm.PipelineVM()
        try:
            vm.setup()
            backend = TestBackend(step_mode=True)
            vm.set_backend(backend)

            # run once w/o a spec
            backend.next_step()

            # run with a spec
            spec = pipeline_vm.PipelineVMSpec()
            spec.buffers.append(pipeline_vm.FloatBufferRef('foo', 0, 1))
            spec.opcodes.append(
                pipeline_vm.OpCode('SET_FLOAT', offset=0, value=12))
            vm.set_spec(spec)
            backend.next_step()

            # replace spec
            spec = pipeline_vm.PipelineVMSpec()
            spec.buffers.append(pipeline_vm.FloatBufferRef('foo', 0, 1))
            spec.opcodes.append(
                pipeline_vm.OpCode('SET_FLOAT', offset=0, value=14))
            vm.set_spec(spec)
            backend.next_step()

            # run once w/o a spec
            vm.set_spec(None)
            backend.next_step()

        finally:
            vm.cleanup()

    async def test_run_vm(self):
        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('float', 0, 1))
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf1', 4, 256))
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf2', 1028, 256))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'SET_FLOAT',
                offset=0, value=12))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'COPY_BUFFER',
                src_offset=4, dest_offset=1024, length=1024))

        vm = pipeline_vm.PipelineVM()
        vm.setup_spec(spec)

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 128

        vm.run_vm(spec, ctxt)

    async def test_OUTPUT_STEREO(self):
        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('bufl', 0, 4))
        spec.buffers.append(pipeline_vm.FloatBufferRef('bufr', 16, 4))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'OUTPUT_STEREO', offset_l=0, offset_r=16, num_samples=4))

        backend = TestBackend()

        vm = pipeline_vm.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('bufl', struct.pack('=ffff', 1, 2, 3, 4))
        vm.set_buffer_bytes('bufr', struct.pack('=ffff', 5, 6, 7, 8))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt)

        self.assertEqual(len(backend.written_frames), 1)
        layout, num_samples, samples = backend.written_frames[0]
        self.assertEqual(layout, resample.AV_CH_LAYOUT_STEREO)
        self.assertEqual(num_samples, 4)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0], struct.pack('=ffff', 1, 2, 3, 4))
        self.assertEqual(samples[1], struct.pack('=ffff', 5, 6, 7, 8))

    async def test_NOISE(self):
        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf', 0, 4))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'NOISE', offset=0, num_samples=4))

        backend = TestBackend()

        vm = pipeline_vm.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt)

        for sample in struct.unpack('=ffff', vm.get_buffer_bytes('buf')):
            self.assertGreaterEqual(sample, -1.0)
            self.assertLessEqual(sample, 1.0)

    async def test_MUL(self):
        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf', 0, 4))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'MUL', offset=0, num_samples=4, factor=2))

        backend = TestBackend()

        vm = pipeline_vm.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('buf', struct.pack('=ffff', 1, 2, 3, 4))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt)

        self.assertEqual(
            vm.get_buffer_bytes('buf'),
            struct.pack('=ffff', 2, 4, 6, 8))

    async def test_MIX(self):
        spec = pipeline_vm.PipelineVMSpec()
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf1', 0, 4))
        spec.buffers.append(pipeline_vm.FloatBufferRef('buf2', 16, 4))
        spec.opcodes.append(
            pipeline_vm.OpCode(
                'MIX', src_offset=16, dest_offset=0, num_samples=4, factor=0.5))

        backend = TestBackend()

        vm = pipeline_vm.PipelineVM()
        vm.setup_spec(spec)
        vm.setup_backend(backend)

        vm.set_buffer_bytes('buf1', struct.pack('=ffff', 1, 2, 3, 4))
        vm.set_buffer_bytes('buf2', struct.pack('=ffff', 2, 2, 4, 4))

        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 4

        vm.run_vm(spec, ctxt)

        self.assertEqual(
            struct.unpack('=ffff', vm.get_buffer_bytes('buf1')),
            (2.0, 3.0, 5.0, 6.0))

    async def test_CALL(self):
        vm = pipeline_vm.PipelineVM()

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

            spec = pipeline_vm.PipelineVMSpec()
            spec.buffers.append(pipeline_vm.FloatBufferRef('buf1', 0, 4))
            spec.buffers.append(pipeline_vm.FloatBufferRef('buf2', 16, 4))
            spec.nodes.append(['node', [('in', 'buf1'), ('out', 'buf2')]])
            spec.opcodes.append(
                pipeline_vm.OpCode(
                    'CALL', node_idx=0))
            vm.setup_spec(spec)

            backend = TestBackend()
            vm.setup_backend(backend)

            vm.set_buffer_bytes('buf1', struct.pack('=ffff', 20, 40, 60, 80))

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 4

            vm.run_vm(spec, ctxt)

            self.assertEqual(
                struct.unpack('=ffff', vm.get_buffer_bytes('buf2')),
                (2.0, 4.0, 6.0, 8.0))

        finally:
            await node.cleanup()


    # async def test_play(self):
    #     vm = pipeline_vm.PipelineVM()
    #     try:
    #         vm.setup()
    #         vm.set_backend(backend.PyAudioBackend())

    #         spec = pipeline_vm.PipelineVMSpec()
    #         spec.buffers.append(pipeline_vm.FloatBufferRef('buf1', 0, 128))
    #         spec.buffers.append(pipeline_vm.FloatBufferRef('buf2', 512, 128))
    #         spec.opcodes.append(
    #             pipeline_vm.OpCode(
    #                 'SINE', offset=0, num_samples=128, freq=440))
    #         spec.opcodes.append(
    #             pipeline_vm.OpCode(
    #                 'MUL', offset=0, num_samples=128, factor=0.8))
    #         spec.opcodes.append(
    #             pipeline_vm.OpCode(
    #                 'NOISE', offset=512, num_samples=128))
    #         spec.opcodes.append(
    #             pipeline_vm.OpCode(
    #                 'MIX', src_offset=512, dest_offset=0, num_samples=128, factor=0.2))
    #         spec.opcodes.append(
    #             pipeline_vm.OpCode(
    #                 'OUTPUT_STEREO', offset_l=0, offset_r=0, num_samples=128))
    #         vm.set_spec(spec)

    #         time.sleep(2.0)

    #     finally:
    #         vm.cleanup()


if __name__ == '__main__':
    unittest.main()
