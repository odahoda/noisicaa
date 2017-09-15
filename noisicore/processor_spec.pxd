from libc.stdint cimport int64_t
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from .status cimport *

cdef extern from "noisicore/processor_spec.h" namespace "noisicaa" nogil:
    enum PortType:
        audio
        aRateControl
        kRateControl
        atomData

    enum PortDirection:
        Input
        Output

    cppclass PortSpec:
        string name() const
        PortType type() const
        PortDirection direction() const

    cppclass ParameterSpec:
        enum ParameterType:
            String
            Int
            Float

        string name() const
        ParameterType type() const

    cppclass StringParameterSpec(ParameterSpec):
        StringParameterSpec(const string& name, const string& default_value)
        string default_value() const

    cppclass IntParameterSpec(ParameterSpec):
        IntParameterSpec(const string& name, int64_t default_value)
        int64_t default_value() const

    cppclass FloatParameterSpec(ParameterSpec):
        FloatParameterSpec(const string& name, float default_value)
        float default_value() const


    cppclass ProcessorSpec:
        ProcessorSpec()

        Status add_port(const string& name, PortType type, PortDirection direction);
        int num_ports() const
        PortSpec get_port(int idx) const

        Status add_parameter(ParameterSpec* param)
        StatusOr[ParameterSpec*] get_parameter(const string& name) const


cdef class PyProcessorSpec(object):
    cdef unique_ptr[ProcessorSpec] __spec_ptr
    cdef ProcessorSpec* __spec

    cdef ProcessorSpec* ptr(self)
    cdef ProcessorSpec* release(self)
