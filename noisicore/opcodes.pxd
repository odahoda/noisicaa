from libcpp.string cimport string
from libcpp.vector cimport vector
from libc.stdint cimport int64_t

from .vm cimport *

cdef extern from "noisicore/opcodes.h" namespace "noisicaa" nogil:
    enum OpCode:
        NOOP
        END
        COPY
        CLEAR
        MIX
        MUL
        SET_FLOAT
        OUTPUT
        FETCH_BUFFER
        FETCH_MESSAGES
        FETCH_PARAMETER
        NOISE
        SINE
        MIDI_MONKEY,
        CONNECT_PORT
        CALL
        LOG_RMS
        LOG_ATOM
        NUM_OPCODES

    enum OpArgType:
        INT
        FLOAT
        STRING

    cppclass OpArg:
        OpArg(int64_t value)
        OpArg(float value)
        OpArg(const string& value)
        OpArgType type()
        int64_t int_value() const
        float float_value() const
        const string& string_value() const

    struct ProgramState
    ctypedef Status (*OpFunc)(ProgramState*, const vector[OpArg]& args)

    struct OpSpec:
        OpCode opcode
        const char* name
        const char* argspec
        OpFunc init
        OpFunc run

    cdef OpSpec opspecs[]
