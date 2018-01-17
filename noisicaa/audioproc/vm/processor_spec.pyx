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

from noisicaa import node_db

cdef class PyProcessorSpec(object):
    def __init__(self):
        self.__spec_ptr.reset(new ProcessorSpec())
        self.__spec = self.__spec_ptr.get()

    cdef ProcessorSpec* ptr(self):
        return self.__spec

    cdef ProcessorSpec* release(self):
        return self.__spec_ptr.release()

    def init(self, description):
        cdef:
            PortType port_type
            PortDirection direction

        assert isinstance(description, node_db.ProcessorDescription)

        for port in description.ports:
            port_type = {
                node_db.PortType.Audio: PortType.audio,
                node_db.PortType.KRateControl: PortType.kRateControl,
                node_db.PortType.ARateControl: PortType.aRateControl,
                node_db.PortType.Events: PortType.atomData}[port.port_type]

            direction = {
                node_db.PortDirection.Input: PortDirection.Input,
                node_db.PortDirection.Output: PortDirection.Output,
                }[port.direction]

            name = port.name
            if isinstance(name, str):
                name = name.encode('ascii')
            assert isinstance(name, bytes)

            check(self.__spec.add_port(name, port_type, direction))

        for param in description.parameters:
            name = param.name
            if isinstance(name, str):
                name = name.encode('ascii')
            assert isinstance(name, bytes)

            if param.param_type in (node_db.ParameterType.String,
                                    node_db.ParameterType.Text,
                                    node_db.ParameterType.Path):
                default = param.default
                if isinstance(default, str):
                    default = default.encode('utf-8')
                assert isinstance(default, bytes)
                check(self.__spec.add_parameter(new StringParameterSpec(name, default)))

            elif param.param_type == node_db.ParameterType.Int:
                check(self.__spec.add_parameter(new IntParameterSpec(name, param.default)))

            elif param.param_type == node_db.ParameterType.Float:
                check(self.__spec.add_parameter(new FloatParameterSpec(name, param.default)))

            else:
                raise TypeError(type(param).__name__)
