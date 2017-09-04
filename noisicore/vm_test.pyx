from libcpp.memory cimport unique_ptr
from libcpp.string cimport string
from .status cimport *
from .spec cimport *
from .block_context cimport *
from .vm cimport *
from .backend cimport *
from .processor cimport *
from .processor_spec cimport *
from .buffers cimport *
from .host_data cimport *

import unittest
import sys


class TestVM(unittest.TestCase):
    # TODO
    # - test that end_block is called when there was an error

    def test_playback(self):
        cdef:
            Status status
            unique_ptr[HostData] host_data
            BackendSettings backend_settings
            Spec* spec
            BlockContext ctxt

        host_data.reset(new HostData())

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.get()))
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            status = vm.set_backend(Backend.create(b'null', backend_settings))
            self.assertFalse(status.is_error())

            spec = new Spec()
            spec.append_buffer(b'buf1', new FloatAudioBlock())
            spec.append_buffer(b'buf2', new FloatAudioBlock())
            spec.append_opcode(OpCode.NOISE, b'buf1')
            spec.append_opcode(OpCode.MUL, b'buf1', 0.3)
            spec.append_opcode(OpCode.CLEAR, b'buf2')
            spec.append_opcode(OpCode.MIX, b'buf1', b'buf2')
            spec.append_opcode(OpCode.OUTPUT, b'buf2', b'left')
            spec.append_opcode(OpCode.OUTPUT, b'buf2', b'right')
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            for _ in range(100):
                status = vm.process_block(&ctxt)
                self.assertFalse(status.is_error(), status.message())

        finally:
            vm.cleanup()

    def test_foo(self):
        cdef:
            Status status
            unique_ptr[HostData] host_data
            BackendSettings backend_settings
            Spec* spec
            Buffer* buf
            float* data
            BlockContext ctxt

        host_data.reset(new HostData())

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.get()))
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            status = vm.set_backend(Backend.create(b'null', backend_settings))
            self.assertFalse(status.is_error())

            spec = new Spec()
            spec.append_buffer(b'buf1', new FloatAudioBlock())
            spec.append_buffer(b'buf2', new FloatAudioBlock())
            spec.append_opcode(OpCode.MIX, b'buf1', b'buf2')
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf1')
            self.assertEqual(buf.size(), 1024)
            data = <float*>buf.data()
            data[0] = 1.0
            data[1] = 2.0

            buf = vm.get_buffer(b'buf2')
            self.assertEqual(buf.size(), 1024)
            data = <float*>buf.data()
            data[0] = 4.0
            data[1] = 5.0

            status = vm.process_block(&ctxt)
            self.assertFalse(status.is_error(), status.message())

            buf = vm.get_buffer(b'buf2')
            data = <float*>buf.data()
            self.assertEqual(data[0], 5.0)
            self.assertEqual(data[1], 7.0)

        finally:
            vm.cleanup()

    def test_processor(self):
        cdef:
            Status status
            unique_ptr[HostData] host_data
            BackendSettings backend_settings
            Spec* spec
            Buffer* buf
            float* data
            BlockContext ctxt
            unique_ptr[ProcessorSpec] processor_spec
            unique_ptr[Processor] processor_ptr
            Processor* processor

        host_data.reset(new HostData())

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.get()))
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            status = vm.set_backend(Backend.create(b'null', backend_settings))
            self.assertFalse(status.is_error())

            processor_spec.reset(new ProcessorSpec())
            processor_spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
            processor_spec.get().add_port(b'in', PortType.audio, PortDirection.Input)
            processor_spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
            processor_spec.get().add_parameter(new StringParameterSpec(b'ladspa_library_path', b'/usr/lib/ladspa/amp.so'))
            processor_spec.get().add_parameter(new StringParameterSpec(b'ladspa_plugin_label', b'amp_mono'))

            processor_ptr.reset(vm.create_processor(b'ladspa'))
            self.assertTrue(processor_ptr.get() != NULL)
            processor = processor_ptr.get()

            status = processor.setup(processor_spec.release())
            self.assertFalse(status.is_error(), status.message())

            status = vm.add_processor(processor_ptr.release())
            self.assertFalse(status.is_error(), status.message())

            spec = new Spec()
            spec.append_buffer(b'gain', new Float())
            spec.append_buffer(b'in', new FloatAudioBlock())
            spec.append_buffer(b'out', new FloatAudioBlock())
            spec.append_processor(processor)
            spec.append_opcode(OpCode.CONNECT_PORT, processor, 0, b'gain')
            spec.append_opcode(OpCode.CONNECT_PORT, processor, 1, b'in')
            spec.append_opcode(OpCode.CONNECT_PORT, processor, 2, b'out')
            spec.append_opcode(OpCode.CALL, processor)
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'gain')
            (<float*>buf.data())[0] = 0.5

            buf = vm.get_buffer(b'in')
            data = <float*>buf.data()
            data[0] = 1.0
            data[1] = 2.0
            data[2] = 3.0
            data[3] = 4.0

            status = vm.process_block(&ctxt)
            self.assertFalse(status.is_error(), status.message())

            buf = vm.get_buffer(b'out')
            data = <float*>buf.data()
            self.assertEqual(data[0], 0.5)
            self.assertEqual(data[1], 1.0)
            self.assertEqual(data[2], 1.5)
            self.assertEqual(data[3], 2.0)

        finally:
            vm.cleanup()

    def test_block_size_changed(self):
        cdef:
            Status status
            unique_ptr[HostData] host_data
            BackendSettings backend_settings
            Spec* spec
            Buffer* buf
            BlockContext ctxt

        host_data.reset(new HostData())

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.get()))
        cdef VM* vm = vmptr.get()
        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            status = vm.set_backend(Backend.create(b'null', backend_settings))
            self.assertFalse(status.is_error())

            status = vm.set_block_size(1024)
            self.assertFalse(status.is_error())

            spec = new Spec()
            spec.append_buffer(b'buf1', new FloatAudioBlock())
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf1')
            self.assertEqual(buf.size(), 4096)

            status = vm.set_block_size(256)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf1')
            self.assertEqual(buf.size(), 4096)

            status = vm.process_block(&ctxt)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf1')
            self.assertEqual(buf.size(), 1024)

        finally:
            vm.cleanup()


if __name__ == '__main__':
    test_loader = unittest.TestLoader()
    suite = test_loader.loadTestsFromTestCase(TestVM)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
