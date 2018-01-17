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
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport *

cdef extern from "noisicaa/audioproc/vm/processor_spec.h" namespace "noisicaa" nogil:
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
