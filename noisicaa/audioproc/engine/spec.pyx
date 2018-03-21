# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from libc.string cimport strlen
from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport check, Status, StatusOr
from noisicaa.audioproc.public.musical_time cimport PyMusicalDuration
from .buffers cimport PyBufferType
from .control_value cimport PyControlValue
from .opcodes cimport OpCode, OpSpec, OpArgType, OpArg, opspecs
from .processor cimport PyProcessor
from .realm cimport PyRealm


opcode_map = {
    'NOOP':                OpCode.NOOP,
    'END':                 OpCode.END,
    'CALL_CHILD_REALM':    OpCode.CALL_CHILD_REALM,
    'COPY':                OpCode.COPY,
    'CLEAR':               OpCode.CLEAR,
    'MIX':                 OpCode.MIX,
    'MUL':                 OpCode.MUL,
    'SET_FLOAT':           OpCode.SET_FLOAT,
    'FETCH_MESSAGES':      OpCode.FETCH_MESSAGES,
    'FETCH_CONTROL_VALUE': OpCode.FETCH_CONTROL_VALUE,
    'POST_RMS':            OpCode.POST_RMS,
    'NOISE':               OpCode.NOISE,
    'SINE':                OpCode.SINE,
    'MIDI_MONKEY':         OpCode.MIDI_MONKEY,
    'CONNECT_PORT':        OpCode.CONNECT_PORT,
    'CALL':                OpCode.CALL,
    'LOG_RMS':             OpCode.LOG_RMS,
    'LOG_ATOM':            OpCode.LOG_ATOM,
}

opname = {
    opcode: name
    for name, opcode in opcode_map.items()
}

cdef class PySpec(object):
    def __init__(self):
        self.__spec_ptr.reset(new Spec())
        self.__spec = self.__spec_ptr.get()

    cdef Spec* get(self) nogil:
        return self.__spec

    cdef Spec* release(self) nogil:
        return self.__spec_ptr.release()

    def dump(self):
        out = []

        # out.append('buffers:')
        # cdef BufferType* buf
        # for idx in range(self.__spec.num_buffers()):
        #     buf = self.__spec.get_buffer(idx)
        #     out.append('  % 3d %d' % (idx, buf.size()))

        # out += 'processors:\n'
        # for idx, node_id in enumerate(self.processor):
        #     out += '% 3d %s\n' % (idx, node_id)

        out.append('opcodes:')
        cdef OpCode opcode
        cdef const OpArg* oparg
        for idx in range(self.__spec.num_ops()):
            opcode = self.__spec.get_opcode(idx)
            opspec = opspecs[<int>opcode]
            args = []
            for argidx in range(strlen(opspec.argspec)):
                oparg = &self.__spec.get_oparg(idx, argidx)
                if oparg.type() == OpArgType.INT:
                    args.append('i:%d' % oparg.int_value())
                elif oparg.type() == OpArgType.FLOAT:
                    args.append('f:%f' % oparg.float_value())
                elif oparg.type() == OpArgType.STRING:
                    args.append('s:%r' % oparg.string_value().decode('utf-8'))
                else:
                    args.append('??')

            out.append('  % 3d %s(%s)' % (idx, opname[opcode], ', '.join(args)))

        return '\n'.join(out)

    @property
    def bpm(self):
        return int(self.__spec.bpm())

    @bpm.setter
    def bpm(self, value):
        self.__spec.set_bpm(value)

    @property
    def duration(self):
        return PyMusicalDuration.create(self.__spec.duration())

    @duration.setter
    def duration(self, PyMusicalDuration value):
        self.__spec.set_duration(value.get())

    def append_buffer(self, name, PyBufferType buf_type):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert(isinstance(name, bytes))
        check(self.__spec.append_buffer(name, buf_type.release()))

    def append_control_value(self, PyControlValue cv):
        check(self.__spec.append_control_value(cv.get()))

    def append_processor(self, PyProcessor processor):
        check(self.__spec.append_processor(processor.get()))

    def append_child_realm(self, PyRealm child_realm):
        check(self.__spec.append_child_realm(child_realm.get()))

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
                stor_int = self.__spec.get_processor_idx((<PyProcessor>value).get())
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            elif spec == 'c':
                if not isinstance(value, PyControlValue):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected PyControlValue, got %s" % (
                            opcode, idx, type(value).__name__))
                stor_int = self.__spec.get_control_value_idx((<PyControlValue>value).get())
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            elif spec == 'r':
                if not isinstance(value, PyRealm):
                    raise TypeError(
                        "OpCode %s, arg #%d: Expected PyRealm, got %s" % (
                            opcode, idx, type(value).__name__))
                stor_int = self.__spec.get_child_realm_idx((<PyRealm>value).get())
                check(stor_int)
                opargs.push_back(OpArg(<int64_t>(stor_int.result())))
            else:
                assert False, spec

        check(self.__spec.append_opcode_args(op, opargs))
