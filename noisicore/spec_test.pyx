from libcpp cimport bool
from libcpp.string cimport string
from libcpp.vector cimport vector
from libc.stdint cimport int64_t

from .status cimport *
from .spec cimport *

import unittest
import sys


class TestSpec(unittest.TestCase):
    def test_foo(self):
        cdef:
            Status status
            Spec spec
            vector[Instruction] opcodes
            const OpArg* arg

        status = spec.append_opcode(OpCode.NOOP)
        self.assertFalse(status.is_error())

        status = spec.append_opcode(OpCode.COPY, 1, 2)
        self.assertFalse(status.is_error())

        status = spec.append_opcode(OpCode.FETCH_ENTITY, b'abcd', 3)
        self.assertFalse(status.is_error())

        self.assertEqual(spec.num_ops(), 3)

        self.assertEqual(spec.get_opcode(0), OpCode.NOOP)

        self.assertEqual(spec.get_opcode(1), OpCode.COPY)
        arg = &spec.get_oparg(1, 0)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 1)
        arg = &spec.get_oparg(1, 1)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 2)

        self.assertEqual(spec.get_opcode(2), OpCode.FETCH_ENTITY)
        arg = &spec.get_oparg(2, 0)
        self.assertEqual(arg.type(), OpArgType.STRING)
        self.assertEqual(arg.string_value(), b'abcd')
        arg = &spec.get_oparg(2, 1)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 3)


if __name__ == '__main__':
    test_loader = unittest.TestLoader()
    suite = test_loader.loadTestsFromTestCase(TestSpec)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
