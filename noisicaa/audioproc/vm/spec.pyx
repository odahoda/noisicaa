# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from libc.stdint cimport int64_t
from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport *
from .buffers cimport *
from .control_value cimport *
from .opcodes cimport *
from .processor cimport *

opcode_map = {
    'NOOP':                OpCode.NOOP,
    'END':                 OpCode.END,
    'COPY':                OpCode.COPY,
    'CLEAR':               OpCode.CLEAR,
    'MIX':                 OpCode.MIX,
    'MUL':                 OpCode.MUL,
    'SET_FLOAT':           OpCode.SET_FLOAT,
    'OUTPUT':              OpCode.OUTPUT,
    'FETCH_BUFFER':        OpCode.FETCH_BUFFER,
    'FETCH_MESSAGES':      OpCode.FETCH_MESSAGES,
    'FETCH_CONTROL_VALUE': OpCode.FETCH_CONTROL_VALUE,
    'NOISE':               OpCode.NOISE,
    'SINE':                OpCode.SINE,
    'MIDI_MONKEY':         OpCode.MIDI_MONKEY,
    'CONNECT_PORT':        OpCode.CONNECT_PORT,
    'CALL':                OpCode.CALL,
    'LOG_RMS':             OpCode.LOG_RMS,
    'LOG_ATOM':            OpCode.LOG_ATOM,
}

cdef class PySpec(object):
    def __init__(self):
        self.__spec_ptr.reset(new Spec())
        self.__spec = self.__spec_ptr.get()

    cdef Spec* ptr(self):
        return self.__spec

    cdef Spec* release(self):
        return self.__spec_ptr.release()

    def dump(self):
        out = ''

        # out += 'buffers:\n'
        # for idx, buf in enumerate(self.buffers):
        #     out += '% 3d %s\n' % (idx, buf)

        # out += 'processors:\n'
        # for idx, node_id in enumerate(self.processor):
        #     out += '% 3d %s\n' % (idx, node_id)

        # out += 'opcodes:\n'
        # for idx, opcode in enumerate(self.opcodes):
        #     out += '% 3d %s\n' % (idx, opcode)

        return out

    def append_buffer(self, name, PyBufferType buf_type):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert(isinstance(name, bytes))
        check(self.__spec.append_buffer(name, buf_type.cpptype.release()))

    def append_control_value(self, PyControlValue cv):
        check(self.__spec.append_control_value(cv.ptr()))

    def append_opcode(self, opcode, *args):
        cdef StatusOr[int] stor_int

        cdef OpCode op = opcode_map[opcode]
        cdef OpSpec opspec = opspecs[<int>op]
        argspec = bytes(opspec.argspec).decode('ascii')
        assert len(args) == len(argspec), (args, argspec)

        cdef vector[OpArg] opargs
        for idx, (spec, value) in enumerate(zip(argspec, args)):
            if spec == 'b':
                if isinstance(value, str):
                    value = value.encode('ascii')
                if not isinstance(value, bytes):
                    raise TypeError(
                        "OpCode %s, arg #%d: Excepted str/bytes, got %s" % (
                            opcode, idx, type(value).__name__))
                stor_int = self.__spec.get_buffer_idx(value)
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            elif spec == 'f':
                if not isinstance(value, float):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected float, got %s" % (
                            opcode, idx, type(value).__name__))
                opargs.push_back(OpArg(<float>value))
            elif spec == 'i':
                if not isinstance(value, int):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected int, got %s" % (
                            opcode, idx, type(value).__name__))
                opargs.push_back(OpArg(<int64_t>value))
            elif spec == 's':
                if isinstance(value, str):
                    value = value.encode('utf-8')
                if not isinstance(value, bytes):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected str/bytes, got %s" % (
                            opcode, idx, type(value).__name__))
                opargs.push_back(OpArg(<string>value))
            elif spec == 'p':
                if not isinstance(value, PyProcessor):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected PyProcessor, got %s" % (
                            opcode, idx, type(value).__name__))
                stor_int = self.__spec.get_processor_idx((<PyProcessor>value).ptr())
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            elif spec == 'c':
                if not isinstance(value, PyControlValue):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected PyControlValue, got %s" % (
                            opcode, idx, type(value).__name__))
                stor_int = self.__spec.get_control_value_idx((<PyControlValue>value).ptr())
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            else:
                assert False, spec

        check(self.__spec.append_opcode_args(op, opargs))

    def append_processor(self, PyProcessor processor):
        check(self.__spec.append_processor(processor.ptr()))
