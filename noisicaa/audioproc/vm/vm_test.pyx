from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

import unittest
import sys

from noisicaa import constants
from noisicaa.core.status cimport *
from .spec cimport *
from .block_context cimport *
from .vm cimport *
from .backend cimport *
from .processor cimport *
from .processor_spec cimport *
from .buffers cimport *
from .host_data cimport *


class TestVM(unittest.TestCase):
    # TODO
    # - test that end_block is called when there was an error

    def test_playback(self):
        cdef PyHostData host_data = PyHostData()
        host_data.setup()

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.ptr()))
        cdef VM* vm = vmptr.get()

        check(vm.setup())

        cdef BackendSettings backend_settings
        backend_settings.block_size = 4096
        cdef StatusOr[Backend*] stor_backend = Backend.create(
            constants.TEST_OPTS.PLAYBACK_BACKEND.encode('ascii'), backend_settings)
        check(stor_backend)
        check(vm.set_backend(stor_backend.result()))

        cdef ProcessorSpec* fluidsynth_spec = new ProcessorSpec()
        fluidsynth_spec.add_port(b'in', PortType.atomData, PortDirection.Input)
        fluidsynth_spec.add_port(b'out:left', PortType.audio, PortDirection.Output)
        fluidsynth_spec.add_port(b'out:right', PortType.audio, PortDirection.Output)
        fluidsynth_spec.add_parameter(new StringParameterSpec(b'soundfont_path', b'/usr/share/sounds/sf2/TimGM6mb.sf2'))
        fluidsynth_spec.add_parameter(new IntParameterSpec(b'bank', 0))
        fluidsynth_spec.add_parameter(new IntParameterSpec(b'preset', 0))

        cdef StatusOr[Processor*] stor_fluidsynth_proc = Processor.create(
            host_data.ptr(), b'fluidsynth')
        check(stor_fluidsynth_proc)
        cdef Processor* fluidsynth_proc = stor_fluidsynth_proc.result()
        check(fluidsynth_proc.setup(fluidsynth_spec))
        check(vm.add_processor(fluidsynth_proc))

        cdef Spec* spec = new Spec()
        check(spec.append_buffer(b'noise_out', new FloatAudioBlock()))
        check(spec.append_buffer(b'fluid_in', new AtomData()))
        check(spec.append_buffer(b'fluid_out_left', new FloatAudioBlock()))
        check(spec.append_buffer(b'fluid_out_right', new FloatAudioBlock()))
        check(spec.append_buffer(b'out_left', new FloatAudioBlock()))
        check(spec.append_buffer(b'out_right', new FloatAudioBlock()))
        check(spec.append_processor(fluidsynth_proc))
        check(spec.append_opcode(OpCode.CLEAR, b'out_left'))
        check(spec.append_opcode(OpCode.CLEAR, b'out_right'))
        check(spec.append_opcode(OpCode.NOISE, b'noise_out'))
        check(spec.append_opcode(OpCode.MUL, b'noise_out', 0.1))
        check(spec.append_opcode(OpCode.MIX, b'noise_out', b'out_left'))
        check(spec.append_opcode(OpCode.MIX, b'noise_out', b'out_right'))
        check(spec.append_opcode(OpCode.MIDI_MONKEY, b'fluid_in', 0.1))
        check(spec.append_opcode(OpCode.CONNECT_PORT, fluidsynth_proc, 0, b'fluid_in'))
        check(spec.append_opcode(OpCode.CONNECT_PORT, fluidsynth_proc, 1, b'fluid_out_left'))
        check(spec.append_opcode(OpCode.CONNECT_PORT, fluidsynth_proc, 2, b'fluid_out_right'))
        check(spec.append_opcode(OpCode.CALL, fluidsynth_proc))
        check(spec.append_opcode(OpCode.MIX, b'fluid_out_left', b'out_left'))
        check(spec.append_opcode(OpCode.MIX, b'fluid_out_right', b'out_right'))
        check(spec.append_opcode(OpCode.OUTPUT, b'out_left', b'left'))
        check(spec.append_opcode(OpCode.OUTPUT, b'out_right', b'right'))
        check(vm.set_spec(spec))

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.sample_pos = 0
        for _ in range(100):
            check(vm.process_block(ctxt.get()))
            ctxt.sample_pos += ctxt.block_size

        vm.cleanup()

    def test_foo(self):
        cdef PyHostData host_data = PyHostData()
        host_data.setup()

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.ptr()))
        cdef VM* vm = vmptr.get()
        check(vm.setup())

        cdef BackendSettings backend_settings
        backend_settings.block_size = 256
        cdef StatusOr[Backend*] stor_backend = Backend.create(b"null", backend_settings)
        check(stor_backend)
        check(vm.set_backend(stor_backend.result()))

        cdef PyBlockContext ctxt = PyBlockContext()

        cdef Spec* spec = new Spec()
        spec.append_buffer(b'buf1', new FloatAudioBlock())
        spec.append_buffer(b'buf2', new FloatAudioBlock())
        spec.append_opcode(OpCode.MIX, b'buf1', b'buf2')
        check(vm.set_spec(spec))
        check(vm.process_block(ctxt.get()))

        cdef Buffer* buf = vm.get_buffer(b'buf1')
        self.assertEqual(buf.size(), 1024)
        cdef float* data = <float*>buf.data()
        data[0] = 1.0
        data[1] = 2.0

        buf = vm.get_buffer(b'buf2')
        self.assertEqual(buf.size(), 1024)
        data = <float*>buf.data()
        data[0] = 4.0
        data[1] = 5.0

        check(vm.process_block(ctxt.get()))

        buf = vm.get_buffer(b'buf2')
        data = <float*>buf.data()
        self.assertEqual(data[0], 5.0)
        self.assertEqual(data[1], 7.0)

        vm.cleanup()

    def test_processor(self):
        cdef PyHostData host_data = PyHostData()

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.ptr()))
        cdef VM* vm = vmptr.get()
        check(vm.setup())

        cdef BackendSettings backend_settings
        backend_settings.block_size = 128
        cdef StatusOr[Backend*] stor_backend = Backend.create(b"null", backend_settings)
        check(stor_backend)
        check(vm.set_backend(stor_backend.result()))

        cdef unique_ptr[ProcessorSpec] processor_spec
        processor_spec.reset(new ProcessorSpec())
        processor_spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
        processor_spec.get().add_port(b'in', PortType.audio, PortDirection.Input)
        processor_spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
        processor_spec.get().add_parameter(new StringParameterSpec(b'ladspa_library_path', b'/usr/lib/ladspa/amp.so'))
        processor_spec.get().add_parameter(new StringParameterSpec(b'ladspa_plugin_label', b'amp_mono'))

        cdef StatusOr[Processor*] stor_processor = Processor.create(host_data.ptr(), b'ladspa')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())
        self.assertTrue(processor_ptr.get() != NULL)
        cdef Processor* processor = processor_ptr.get()

        check(processor.setup(processor_spec.release()))
        check(vm.add_processor(processor_ptr.release()))

        cdef Spec* spec = new Spec()
        spec.append_buffer(b'gain', new Float())
        spec.append_buffer(b'in', new FloatAudioBlock())
        spec.append_buffer(b'out', new FloatAudioBlock())
        spec.append_processor(processor)
        spec.append_opcode(OpCode.CONNECT_PORT, processor, 0, b'gain')
        spec.append_opcode(OpCode.CONNECT_PORT, processor, 1, b'in')
        spec.append_opcode(OpCode.CONNECT_PORT, processor, 2, b'out')
        spec.append_opcode(OpCode.CALL, processor)
        check(vm.set_spec(spec))

        cdef PyBlockContext ctxt = PyBlockContext()
        check(vm.process_block(ctxt.get()))

        cdef Buffer* buf = vm.get_buffer(b'gain')
        (<float*>buf.data())[0] = 0.5

        buf = vm.get_buffer(b'in')
        cdef float* data = <float*>buf.data()
        data[0] = 1.0
        data[1] = 2.0
        data[2] = 3.0
        data[3] = 4.0

        check(vm.process_block(ctxt.get()))

        buf = vm.get_buffer(b'out')
        data = <float*>buf.data()
        self.assertEqual(data[0], 0.5)
        self.assertEqual(data[1], 1.0)
        self.assertEqual(data[2], 1.5)
        self.assertEqual(data[3], 2.0)

        vm.cleanup()

    def test_block_size_changed(self):
        cdef PyHostData host_data = PyHostData()

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM(host_data.ptr()))
        cdef VM* vm = vmptr.get()
        check(vm.setup())

        cdef BackendSettings backend_settings
        backend_settings.block_size = 128
        cdef StatusOr[Backend*] stor_backend = Backend.create(b"null", backend_settings)
        check(stor_backend)
        check(vm.set_backend(stor_backend.result()))

        check(vm.set_block_size(1024))

        cdef PyBlockContext ctxt = PyBlockContext()

        cdef Spec* spec = new Spec()
        spec.append_buffer(b'buf1', new FloatAudioBlock())
        check(vm.set_spec(spec))
        check(vm.process_block(ctxt.get()))

        cdef Buffer* buf = vm.get_buffer(b'buf1')
        self.assertEqual(buf.size(), 4096)

        check(vm.set_block_size(256))

        buf = vm.get_buffer(b'buf1')
        self.assertEqual(buf.size(), 4096)

        check(vm.process_block(ctxt.get()))

        buf = vm.get_buffer(b'buf1')
        self.assertEqual(buf.size(), 1024)

        vm.cleanup()
