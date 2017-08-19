from libcpp.memory cimport unique_ptr
from .status cimport *
from .spec cimport *
from .vm cimport *

import unittest
import sys

class TestVM(unittest.TestCase):
    def test_foo(self):
        cdef:
            Status status
            Spec spec

        cdef unique_ptr[VM] vmptr
        vmptr.reset(new VM())
        cdef VM* vm = vmptr.get()

        try:
            status = vm.setup()
            self.assertFalse(status.is_error())

            spec.append_opcode(OpCode.COPY, 1, 2)
            spec.append_opcode(OpCode.FETCH_ENTITY, b'abcd', 3)
            spec.append_opcode(OpCode.COPY, 3, 1)
            spec.append_opcode(OpCode.END)
            spec.append_opcode(OpCode.FETCH_ENTITY, b'dcba', 2)
            status = vm.set_spec(spec)
            self.assertFalse(status.is_error())

            status = vm.process_frame()
            self.assertFalse(status.is_error())

        finally:
            status = vm.cleanup()
            self.assertFalse(status.is_error())


if __name__ == '__main__':
    test_loader = unittest.TestLoader()
    suite = test_loader.loadTestsFromTestCase(TestVM)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
