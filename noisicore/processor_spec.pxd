from libcpp.string cimport string

from .status cimport *

cdef extern from "processor_spec.h" namespace "noisicaa" nogil:
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

    enum ParameterType:
        String

    cppclass ParameterSpec:
        string name() const
        ParameterType type() const

    cppclass StringParameterSpec(ParameterSpec):
        StringParameterSpec(const string& name, const string& default_value)
        string default_value() const


    cppclass ProcessorSpec:
        ProcessorSpec()

        Status add_port(const string& name, PortType type, PortDirection direction);
        int num_ports() const
        PortSpec get_port(int idx) const

        Status add_parameter(ParameterSpec* param)
        Status get_parameter(const string& name, ParameterSpec** param) const
