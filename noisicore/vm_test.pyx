from libcpp.memory cimport unique_ptr
from .status cimport *
from .spec cimport *
from .buffers cimport *
from .block_context cimport *
from .vm cimport *

import unittest
import sys

class TestVM(unittest.TestCase):
    def test_foo(self):
        cdef:
            Status status
            Spec* spec
            Buffer* buf
            float* data
            BlockContext ctxt

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM())
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
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
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf2')
            data = <float*>buf.data()
            self.assertEqual(data[0], 5.0)
            self.assertEqual(data[1], 7.0)

        finally:
            vm.cleanup()

    def test_block_size_changed(self):
        cdef:
            Status status
            Spec* spec
            Buffer* buf
            BlockContext ctxt

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM())
        cdef VM* vm = vmptr.get()
        try:
            status = vm.setup()
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
