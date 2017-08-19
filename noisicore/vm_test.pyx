from libcpp.memory cimport unique_ptr
from .status cimport *
from .spec cimport *
from .vm cimport *
from .buffers cimport *

import unittest
import sys

class TestVM(unittest.TestCase):
    def test_foo(self):
        cdef:
            Status status
            Spec* spec
            Buffer* buf
            float* data

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM())
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            spec = new Spec()
            spec.append_buffer(b'buf1', new FloatAudioFrame())
            spec.append_buffer(b'buf2', new FloatAudioFrame())
            spec.append_opcode(OpCode.MIX, b'buf1', b'buf2')
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf1')
            self.assertEqual(buf.size(), 512)
            data = <float*>buf.data()
            data[0] = 1.0
            data[1] = 2.0

            buf = vm.get_buffer(b'buf2')
            self.assertEqual(buf.size(), 512)
            data = <float*>buf.data()
            data[0] = 4.0
            data[1] = 5.0

            status = vm.process_frame()
            self.assertFalse(status.is_error())

            buf = vm.get_buffer(b'buf2')
            data = <float*>buf.data()
            self.assertEqual(data[0], 5.0)
            self.assertEqual(data[1], 7.0)

        finally:
            status = vm.cleanup()
            self.assertFalse(status.is_error())


if __name__ == '__main__':
    test_loader = unittest.TestLoader()
    suite = test_loader.loadTestsFromTestCase(TestVM)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
