from libcpp cimport bool
from libcpp.string cimport string
from libcpp.vector cimport vector
from libc.stdint cimport int64_t

import unittest
import sys

from noisicaa.core.status cimport *
from .buffers cimport *
from .spec cimport *


class TestSpec(unittest.TestCase):
    def test_buffers(self):
        cdef:
            Status status
            Spec spec
            const BufferType *type

        spec.append_buffer(b'buf1', new FloatAudioBlock())
        spec.append_buffer(b'buf2', new Float())
        self.assertEqual(spec.num_buffers(), 2)
        self.assertEqual(spec.get_buffer_idx(b'buf1').result(), 0)
        self.assertEqual(spec.get_buffer_idx(b'buf2').result(), 1)

    def test_opcodes(self):
        cdef:
            Status status
            Spec spec
            const OpArg* arg

        spec.append_buffer(b'buf1', new FloatAudioBlock())
        spec.append_buffer(b'buf2', new FloatAudioBlock())
        spec.append_buffer(b'buf3', new FloatAudioBlock())

        status = spec.append_opcode(OpCode.NOOP)
        self.assertFalse(status.is_error())

        status = spec.append_opcode(OpCode.COPY, b'buf1', b'buf2')
        self.assertFalse(status.is_error(), status.message())

        status = spec.append_opcode(OpCode.FETCH_BUFFER, b'abcd', b'buf3')
        self.assertFalse(status.is_error())

        self.assertEqual(spec.num_ops(), 3)

        self.assertEqual(spec.get_opcode(0), OpCode.NOOP)

        self.assertEqual(spec.get_opcode(1), OpCode.COPY)
        arg = &spec.get_oparg(1, 0)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 0)
        arg = &spec.get_oparg(1, 1)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 1)

        self.assertEqual(spec.get_opcode(2), OpCode.FETCH_BUFFER)
        arg = &spec.get_oparg(2, 0)
        self.assertEqual(arg.type(), OpArgType.STRING)
        self.assertEqual(arg.string_value(), b'abcd')
        arg = &spec.get_oparg(2, 1)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 2)
