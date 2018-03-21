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

from libc.stdint cimport uint8_t

from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from . cimport block_context
from . cimport buffers

_UNSET = object()


cdef class PyBackendSettings(object):
    def __init__(
            self, *,
            datastream_address=_UNSET, time_scale=1.0):
        if datastream_address is not _UNSET:
            self.datastream_address = datastream_address
        if time_scale is not _UNSET:
            self.time_scale = time_scale

    cdef BackendSettings get(self):
        return self.__settings

    @property
    def datastream_address(self):
        return bytes(self.__settings.datastream_address).decode('utf-8')

    @datastream_address.setter
    def datastream_address(self, value):
        self.__settings.datastream_address = value.encode('utf-8')

    @property
    def time_scale(self):
        return float(self.__settings.time_scale)

    @time_scale.setter
    def time_scale(self, value):
        self.__settings.time_scale = <float>value


cdef class PyBackend(object):
    def __init__(self, PyHostSystem host_system, name, PyBackendSettings settings):
        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        cdef StatusOr[Backend*] backend = Backend.create(host_system.get(), name, settings.get())
        check(backend)
        self.__backend_ptr.reset(backend.result())
        self.__backend = self.__backend_ptr.get()

    cdef Backend* get(self) nogil:
        return self.__backend

    def setup(self, PyRealm realm):
        cdef Realm* c_realm = realm.get()
        with nogil:
            check(self.__backend.setup(c_realm))

    def cleanup(self):
        # Only do cleanup, when we still own the backend.
        cdef Backend* backend = self.__backend_ptr.get()
        if backend != NULL:
            with nogil:
                backend.cleanup()

    def stop(self):
        with nogil:
            self.__backend.stop()

    def stopped(self):
        cdef bool c_result
        with nogil:
            c_result = self.__backend.stopped()
        return c_result

    def release(self):
        with nogil:
            self.__backend.release()

    def released(self):
        cdef bool c_result
        with nogil:
            c_result = self.__backend.released()
        return c_result

    def send_message(self, bytes msg):
        cdef string c_msg = msg
        with nogil:
            check(self.__backend.send_message(c_msg))

    def begin_block(self, block_context.PyBlockContext ctxt):
        with nogil:
            check(self.__backend.begin_block(ctxt.get()))

    def end_block(self, block_context.PyBlockContext ctxt):
        with nogil:
            check(self.__backend.end_block(ctxt.get()))

    def output(self, block_context.PyBlockContext ctxt, str channel, float[:] samples):
        cdef buffers.BufferPtr c_samples = <BufferPtr>&samples[0]
        cdef string c_channel = channel.encode('utf-8')
        with nogil:
            check(self.__backend.output(ctxt.get(), c_channel, c_samples))
