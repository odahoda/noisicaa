#!/usr/bin/python3

import logging
import struct
import threading
import unittest

import noisicore
from noisicaa import constants
from noisicaa import node_db
from noisicaa import audioproc
from .. import nodes
from . import engine

logger = logging.getLogger(__name__)


# class TestBackend(backend.Backend):
#     def __init__(self, step_mode=False):
#         super().__init__()

#         self.written_frames = []
#         self.step_mode = step_mode
#         self.start_step = threading.Event()
#         self.step_done = threading.Event()

#     def begin_frame(self, ctxt):
#         logger.info("Backend.begin_frame()")
#         if self.step_mode:
#             self.start_step.wait()
#             self.start_step.clear()

#     def end_frame(self):
#         logger.info("Backend.end_frame()")
#         if self.step_mode:
#             self.step_done.set()

#     def output(self, channel, samples):
#         logger.info("Backend received frame.")
#         self.written_frames.append([channel, samples])

#     def stop(self):
#         if self.step_mode:
#             self.start_step.set()
#         super().stop()

#     def next_step(self):
#         assert self.step_mode
#         self.start_step.set()
#         self.step_done.wait()
#         self.step_done.clear()


class PipelineVMTest(unittest.TestCase):
    def setUp(self):
        self.host_data = noisicore.HostData()
        self.host_data.setup()

    def tearDown(self):
        self.host_data.cleanup()

    # def test_get_buffer_bytes(self):
    #     vm = engine.PipelineVM()

    #     spec = noisicore.Spec()
    #     spec.buffers.append(buffers.FloatArray(4))
    #     vm.setup_spec(spec)

    #     vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))
    #     self.assertEqual(
    #         vm.get_buffer_bytes(0),
    #         struct.pack('=ffff', 1, 2, 3, 4))

    # def test_vm_thread(self):
    #     vm = engine.PipelineVM()
    #     try:
    #         vm.setup()
    #         be = TestBackend(step_mode=True)
    #         vm.set_backend(be)

    #         # run once w/o a spec
    #         be.next_step()

    #         # run with a spec
    #         spec = noisicore.Spec()
    #         spec.buffers.append(buffers.Float())
    #         spec.opcodes.append(spec.OpCode('SET_FLOAT', buf_idx=0, value=12))
    #         vm.set_spec(spec)
    #         be.next_step()

    #         # replace spec
    #         spec = spec.Spec()
    #         spec.buffers.append(buffers.Float())
    #         spec.opcodes.append(spec.OpCode('SET_FLOAT', buf_idx=0, value=14))
    #         vm.set_spec(spec)
    #         be.next_step()

    #         # run once w/o a spec
    #         vm.set_spec(None)
    #         be.next_step()

    #     finally:
    #         vm.cleanup()

    def test_run_vm(self):
        spec = noisicore.Spec()
        spec.append_buffer('buf1', noisicore.Float())
        spec.append_buffer('buf2', noisicore.FloatAudioBlock())
        spec.append_buffer('buf3', noisicore.FloatAudioBlock())
        spec.append_opcode('SET_FLOAT', 'buf1', 12.0)
        spec.append_opcode('COPY', 'buf2', 'buf3')
        spec.append_opcode('CLEAR', 'buf2')

        vm = engine.PipelineVM(host_data=self.host_data, block_size=4)
        vm.setup(start_thread=False)
        try:
            vm.set_backend('null', block_size=4)
            vm.set_spec(spec)

            ctxt = noisicore.BlockContext()
            ctxt.sample_pos = 0
            ctxt.block_size = 4
            vm.process_block(ctxt)

            vm.set_buffer_bytes('buf2', struct.pack('ffff', 0.0, 0.5, 1.0, 1.5))

            ctxt.sample_pos = 4
            vm.process_block(ctxt)

            self.assertEqual(vm.get_buffer_bytes('buf1'), struct.pack('f', 12.0))
            self.assertEqual(vm.get_buffer_bytes('buf2'), struct.pack('ffff', 0.0, 0.0, 0.0, 0.0))
            self.assertEqual(vm.get_buffer_bytes('buf3'), struct.pack('ffff', 0.0, 0.5, 1.0, 1.5))

        finally:
            vm.cleanup()

    # def test_OUTPUT(self):
    #     vm_spec = spec.PipelineVMSpec()
    #     vm_spec.buffers.append(buffers.FloatArray(4))
    #     vm_spec.opcodes.append(spec.OpCode('OUTPUT', buf_idx=0, channel='center'))

    #     be = TestBackend()

    #     vm = engine.PipelineVM()
    #     vm.setup_spec(vm_spec)
    #     vm.setup_backend(be)

    #     vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))

    #     ctxt = audioproc.FrameContext()
    #     ctxt.sample_pos = 0
    #     ctxt.duration = 4

    #     vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    #     self.assertEqual(len(be.written_frames), 1)
    #     channel, samples = be.written_frames[0]
    #     self.assertEqual(channel, 'center')
    #     self.assertEqual(samples, struct.pack('=ffff', 1, 2, 3, 4))

    # def test_NOISE(self):
    #     vm_spec = spec.PipelineVMSpec()
    #     vm_spec.buffers.append(buffers.FloatArray(4))
    #     vm_spec.opcodes.append(spec.OpCode('NOISE', buf_idx=0))

    #     be = TestBackend()

    #     vm = engine.PipelineVM()
    #     vm.setup_spec(vm_spec)
    #     vm.setup_backend(be)

    #     ctxt = audioproc.FrameContext()
    #     ctxt.sample_pos = 0
    #     ctxt.duration = 4

    #     vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    #     for sample in struct.unpack('=ffff', vm.get_buffer_bytes(0)):
    #         self.assertGreaterEqual(sample, -1.0)
    #         self.assertLessEqual(sample, 1.0)

    # def test_MUL(self):
    #     vm_spec = spec.PipelineVMSpec()
    #     vm_spec.buffers.append(buffers.FloatArray(4))
    #     vm_spec.opcodes.append(spec.OpCode('MUL', buf_idx=0, factor=2))

    #     be = TestBackend()

    #     vm = engine.PipelineVM()
    #     vm.setup_spec(vm_spec)
    #     vm.setup_backend(be)

    #     vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))

    #     ctxt = audioproc.FrameContext()
    #     ctxt.sample_pos = 0
    #     ctxt.duration = 4

    #     vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    #     self.assertEqual(
    #         vm.get_buffer_bytes(0),
    #         struct.pack('=ffff', 2, 4, 6, 8))

    # def test_MIX(self):
    #     vm_spec = spec.PipelineVMSpec()
    #     vm_spec.buffers.append(buffers.FloatArray(4))
    #     vm_spec.buffers.append(buffers.FloatArray(4))
    #     vm_spec.opcodes.append(spec.OpCode('MIX', src_idx=1, dest_idx=0))

    #     be = TestBackend()

    #     vm = engine.PipelineVM()
    #     vm.setup_spec(vm_spec)
    #     vm.setup_backend(be)

    #     vm.set_buffer_bytes(0, struct.pack('=ffff', 1, 2, 3, 4))
    #     vm.set_buffer_bytes(1, struct.pack('=ffff', 2, 2, 4, 4))

    #     ctxt = audioproc.FrameContext()
    #     ctxt.sample_pos = 0
    #     ctxt.duration = 4

    #     vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    #     self.assertEqual(
    #         struct.unpack('=ffff', vm.get_buffer_bytes(0)),
    #         (3.0, 4.0, 7.0, 8.0))

    # def test_CALL(self):
    #     vm = engine.PipelineVM()

    #     description = node_db.NodeDescription(
    #         ports=[
    #             node_db.AudioPortDescription(
    #                 name='in',
    #                 direction=node_db.PortDirection.Input),
    #             node_db.AudioPortDescription(
    #                 name='out',
    #                 direction=node_db.PortDirection.Output),
    #         ],
    #         parameters=[
    #             node_db.InternalParameterDescription(
    #                 name='uri', value='http://lv2plug.in/plugins/eg-amp'),
    #             node_db.FloatParameterDescription(
    #                 name='gain',
    #                 display_name='Gain',
    #                 default=0.0,
    #                 min=-90.0,
    #                 max=24.0),
    #         ])

    #     node = nodes.LV2(description=description, id='node')
    #     node.setup()
    #     try:
    #         node.set_param(gain=-20.0)

    #         vm.add_node(node)

    #         vm_spec = spec.PipelineVMSpec()
    #         vm_spec.buffers.append(buffers.FloatArray(4))
    #         vm_spec.buffers.append(buffers.FloatArray(4))
    #         vm_spec.nodes.append('node')
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'CONNECT_PORT', node_idx=0, port_name='in', buf_idx=0))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'CONNECT_PORT', node_idx=0, port_name='out', buf_idx=1))
    #         vm_spec.opcodes.append(spec.OpCode(
    #             'CALL', node_idx=0))
    #         vm.setup_spec(vm_spec)

    #         be = TestBackend()
    #         vm.setup_backend(be)

    #         vm.set_buffer_bytes(0, struct.pack('=ffff', 20, 40, 60, 80))

    #         ctxt = audioproc.FrameContext()
    #         ctxt.sample_pos = 0
    #         ctxt.duration = 4

    #         vm.run_vm(vm_spec, ctxt, engine.RunAt.INIT)
    #         vm.run_vm(vm_spec, ctxt, engine.RunAt.PERFORMANCE)

    #         self.assertEqual(
    #             struct.unpack('=ffff', vm.get_buffer_bytes(1)),
    #             (2.0, 4.0, 6.0, 8.0))

    #     finally:
    #         node.cleanup()

    def test_play(self):
        vm = engine.PipelineVM(host_data=self.host_data, block_size=256)
        try:
            vm.setup(start_thread=False)
            vm.set_backend(constants.TEST_OPTS.PLAYBACK_BACKEND, block_size=4096)

            spec = noisicore.Spec()
            spec.append_buffer('buf1', noisicore.FloatAudioBlock())
            spec.append_buffer('buf2', noisicore.FloatAudioBlock())
            spec.append_opcode('NOISE', 'buf1')
            spec.append_opcode('MUL', 'buf1', 0.2)
            spec.append_opcode('OUTPUT', 'buf1', 'left')
            spec.append_opcode('NOISE', 'buf2')
            spec.append_opcode('MUL', 'buf2', 0.2)
            spec.append_opcode('OUTPUT', 'buf2', 'right')
            vm.set_spec(spec)

            ctxt = noisicore.BlockContext()
            ctxt.sample_pos = 0
            ctxt.block_size = 256

            for _ in range(20):
                vm.process_block(ctxt)
                ctxt.sample_pos += ctxt.block_size

        finally:
            vm.cleanup()


if __name__ == '__main__':
    unittest.main()
