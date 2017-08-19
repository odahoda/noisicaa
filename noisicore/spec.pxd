from libcpp.vector cimport vector

from .status cimport *
from .buffers cimport *
from .opcodes cimport *

cdef extern from "spec.h" namespace "noisicaa" nogil:
    cppclass Spec:
        Status append_opcode(OpCode opcode, ...)
        int num_ops() const
        OpCode get_opcode(int idx) const
        const OpArg& get_oparg(int idx, int arg) const

        Status append_buffer(const string& name, BufferType* type)
        int num_buffers() const
        const BufferType* get_buffer(int idx) const
        int get_buffer_idx(const string& name) const

