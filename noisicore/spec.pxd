from libcpp.vector cimport vector

from .status cimport *
from .opcodes cimport *

cdef extern from "spec.h" namespace "noisicaa" nogil:
    ctypedef struct Instruction:
        OpCode opcode
        vector[OpArg] args

    cppclass Spec:
        Status append_opcode(OpCode opcode, ...)
        int num_ops() const
        OpCode get_opcode(int idx) const
        const OpArg& get_oparg(int idx, int arg) const
