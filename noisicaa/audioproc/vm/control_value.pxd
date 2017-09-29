from libc.stdint cimport int64_t
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

cdef extern from "noisicaa/audioproc/vm/control_value.h" namespace "noisicaa" nogil:
    enum ControlValueType:
        FloatCV
        IntCV

    cppclass ControlValue:
        ControlValueType type() const
        const string& name() const

    cppclass FloatControlValue(ControlValue):
        FloatControlValue(const string& name, float value)

        float value() const
        void set_value(float value)

    cppclass IntControlValue(ControlValue):
        IntControlValue(const string& name, int64_t value)

        int64_t value() const
        void set_value(int64_t value)


cdef class PyControlValue(object):
    cdef unique_ptr[ControlValue] __cv_ptr
    cdef ControlValue* __cv

    cdef ControlValue* ptr(self)
    cdef ControlValue* release(self)
