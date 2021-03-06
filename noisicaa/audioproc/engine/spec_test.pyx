# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import sys

from libcpp cimport bool
from libcpp.string cimport string
from libcpp.vector cimport vector
from libc.stdint cimport int64_t

from noisidev import unittest
from noisicaa.core.status cimport check
from noisicaa import node_db
from .buffers cimport FloatAudioBlockBuffer, FloatControlValueBuffer
from .spec cimport Spec
from .opcodes cimport OpCode, OpArg, OpArgType


class TestSpec(unittest.TestCase):
    def test_buffers(self):
        cdef Spec spec
        check(spec.append_buffer(b'buf1', new FloatAudioBlockBuffer(node_db.PortDescription.AUDIO)))
        check(spec.append_buffer(b'buf2', new FloatControlValueBuffer()))
        self.assertEqual(spec.num_buffers(), 2)
        self.assertEqual(spec.get_buffer_idx(b'buf1').result(), 0)
        self.assertEqual(spec.get_buffer_idx(b'buf2').result(), 1)

    def test_opcodes(self):
        cdef Spec spec
        check(spec.append_buffer(b'buf1', new FloatAudioBlockBuffer(node_db.PortDescription.AUDIO)))
        check(spec.append_buffer(b'buf2', new FloatAudioBlockBuffer(node_db.PortDescription.AUDIO)))
        check(spec.append_buffer(b'buf3', new FloatAudioBlockBuffer(node_db.PortDescription.AUDIO)))

        check(spec.append_opcode(OpCode.NOOP, vector[OpArg]()))
        cdef vector[OpArg] a
        a.push_back(OpArg(<int64_t>spec.get_buffer_idx(b'buf1').result()))
        a.push_back(OpArg(<int64_t>spec.get_buffer_idx(b'buf2').result()))
        check(spec.append_opcode(OpCode.COPY, a))
        cdef vector[OpArg] b
        b.push_back(OpArg(<int64_t>spec.get_buffer_idx(b'buf3').result()))
        b.push_back(OpArg(<float>0.5))
        check(spec.append_opcode(OpCode.MUL, b))
        self.assertEqual(spec.num_ops(), 3)

        self.assertEqual(spec.get_opcode(0), OpCode.NOOP)

        cdef const OpArg* arg

        self.assertEqual(spec.get_opcode(1), OpCode.COPY)
        arg = &spec.get_oparg(1, 0)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 0)
        arg = &spec.get_oparg(1, 1)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 1)

        self.assertEqual(spec.get_opcode(2), OpCode.MUL)
        arg = &spec.get_oparg(2, 0)
        self.assertEqual(arg.type(), OpArgType.INT)
        self.assertEqual(arg.int_value(), 2)
        arg = &spec.get_oparg(2, 1)
        self.assertEqual(arg.type(), OpArgType.FLOAT)
        self.assertEqual(arg.float_value(), 0.5)
