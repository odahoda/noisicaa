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

cimport cython

import os

from .host_data cimport *
from .processor_spec cimport *


cdef class PyProcessor(object):
    def __init__(self, node_id, PyHostData host_data, name, PyProcessorSpec spec):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        if isinstance(node_id, str):
            node_id = node_id.encode('utf-8')
        assert isinstance(node_id, bytes)

        self.__name = name

        self.__spec = spec

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            node_id, host_data.ptr(), name)
        check(stor_processor)
        self.__processor_ptr.reset(stor_processor.result())
        self.__processor = self.__processor_ptr.get()

    def __str__(self):
        return '%s:%08x' % (self.__name.decode('ascii'), self.__processor.id())
    __repr__ = __str__

    cdef Processor* ptr(self):
        return self.__processor

    cdef Processor* release(self):
        return self.__processor_ptr.release()

    @property
    def id(self):
        return self.__processor.id()

    def setup(self):
        check(self.__processor.setup(self.__spec.release()))

    def cleanup(self):
        # Only do cleanup, when we still own the processor.
        cdef Processor* processor = self.__processor_ptr.get()
        if processor != NULL:
            processor.cleanup()

    def get_string_parameter(self, name):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        cdef StatusOr[string] stor_value = self.__processor.get_string_parameter(name)
        check(stor_value)
        return str(stor_value.result())

    def set_string_parameter(self, name, value):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        if isinstance(value, str):
            value = value.encode('utf-8')
        assert isinstance(value, bytes)

        check(self.__processor.set_string_parameter(name, value))

    def set_parameter(self, name, value):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        if isinstance(value, str):
            check(self.__processor.set_string_parameter(name, value.encode('utf-8')))
        elif isinstance(value, bytes):
            check(self.__processor.set_string_parameter(name, value))
        elif isinstance(value, int):
            check(self.__processor.set_int_parameter(name, value))
        elif isinstance(value, float):
            check(self.__processor.set_float_parameter(name, value))
        else:
            raise TypeError(type(value).__init__)

