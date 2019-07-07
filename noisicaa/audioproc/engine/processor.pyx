# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import enum
import os

cimport cython
from libcpp.string cimport string

from noisicaa.core.status cimport check
from noisicaa.audioproc.public.time_mapper cimport PyTimeMapper
from noisicaa.host_system.host_system cimport PyHostSystem
from .block_context cimport PyBlockContext
from .buffers cimport PyBuffer
from . cimport rtcheck


class State(enum.Enum):
    INACTIVE = ProcessorState.INACTIVE
    SETUP = ProcessorState.SETUP
    RUNNING = ProcessorState.RUNNING
    BROKEN = ProcessorState.BROKEN
    CLEANUP = ProcessorState.CLEANUP


cdef class PyProcessor(object):
    def __init__(self, realm_name, node_id, PyHostSystem host_system, node_description):
        if isinstance(realm_name, str):
            realm_name = realm_name.encode('utf-8')
        if isinstance(node_id, str):
            node_id = node_id.encode('utf-8')
        assert isinstance(node_id, bytes)

        self.__desc = node_description

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            realm_name, node_id, host_system.get(), self.__desc.SerializeToString())
        check(stor_processor)
        self.__processor = stor_processor.result()
        self.__processor.incref()

    def __dealloc__(self):
        if self.__processor != NULL:
            self.__processor.decref()
            self.__processor = NULL

    def __str__(self):
        return '%s:%08x' % (self.__desc.processor.TYPE_NAME(type), self.__processor.id())
    __repr__ = __str__

    cdef Processor* get(self) nogil:
        return self.__processor

    @property
    def id(self):
        return self.__processor.id()

    @property
    def state(self):
        return State(self.__processor.state())

    def setup(self):
        with nogil:
            check(self.__processor.setup())

    def cleanup(self):
        with nogil:
            self.__processor.cleanup()

    def connect_port(self, PyBlockContext ctxt, port_index, PyBuffer buf):
        cdef uint32_t c_port_index = port_index
        with nogil:
            rtcheck.reset_rt_checker_violations()
            rtcheck.enable_rt_checker(1)
            try:
                self.__processor.connect_port(ctxt.get(), c_port_index, buf.get())
            finally:
                rtcheck.enable_rt_checker(0)
        assert rtcheck.rt_checker_violations() == 0

    def process_block(self, PyBlockContext ctxt, PyTimeMapper time_mapper):
        cdef TimeMapper* c_time_mapper = NULL
        if time_mapper is not None:
            c_time_mapper = time_mapper.get()
        with nogil:
            rtcheck.reset_rt_checker_violations()
            rtcheck.enable_rt_checker(1)
            try:
                self.__processor.process_block(ctxt.get(), c_time_mapper)
            finally:
                rtcheck.enable_rt_checker(0)
        assert rtcheck.rt_checker_violations() == 0, \
          "%d RT violation(s) seen" % rtcheck.rt_checker_violations()

    def handle_message(self, msg):
        cdef string msg_serialized = msg.SerializeToString()
        with nogil:
            check(self.__processor.handle_message(msg_serialized))

    def set_parameters(self, parameters):
        cdef string parameters_serialized = parameters.SerializeToString()
        with nogil:
            check(self.__processor.set_parameters(parameters_serialized))

    def set_description(self, desc):
        cdef string desc_serialized = desc.SerializeToString()
        with nogil:
            check(self.__processor.set_description(desc_serialized))
