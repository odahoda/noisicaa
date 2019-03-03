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

from libc.stdint cimport uint8_t
from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore

from noisicaa import core
from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from noisicaa.audioproc.public import engine_notification_pb2
from . cimport block_context
from . cimport buffers

_UNSET = object()


cdef class PyBackend(object):
    def __init__(self, PyHostSystem host_system, name, settings):
        self.notifications = core.Callback()

        if isinstance(name, str):
            name = name.encode('ascii')
        assert isinstance(name, bytes)

        cdef StatusOr[Backend*] backend = Backend.create(
            host_system.get(), name, settings.SerializeToString(),
            self.__notification_callback, <PyObject*>self)
        check(backend)
        self.__backend_ptr.reset(backend.result())
        self.__backend = self.__backend_ptr.get()

    cdef Backend* get(self) nogil:
        return self.__backend

    @staticmethod
    cdef void __notification_callback(void* c_self, const string& notification_serialized) with gil:
        self = <object><PyObject*>c_self

        # Have to stash away any active exception, because otherwise exception handling
        # might get confused.
        # See https://github.com/cython/cython/issues/1877
        cdef PyObject* exc_type
        cdef PyObject* exc_value
        cdef PyObject* exc_trackback
        PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)
        try:
            notification = engine_notification_pb2.EngineNotification()
            notification.ParseFromString(notification_serialized)
            self.notifications.call(notification)

        finally:
            PyErr_Restore(exc_type, exc_value, exc_trackback)

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

    def begin_block(self, block_context.PyBlockContext ctxt):
        with nogil:
            check(self.__backend.begin_block(ctxt.get()))

    def end_block(self, block_context.PyBlockContext ctxt):
        with nogil:
            check(self.__backend.end_block(ctxt.get()))

    def output(self, block_context.PyBlockContext ctxt, str channel, float[:] samples):
        cdef buffers.BufferPtr c_samples = <BufferPtr>&samples[0]
        cdef Backend.Channel c_channel
        if channel == 'left':
            c_channel = Backend.Channel.AUDIO_LEFT
        elif channel == 'right':
            c_channel = Backend.Channel.AUDIO_RIGHT
        elif channel == 'events':
            c_channel = Backend.Channel.EVENTS
        else:
            raise ValueError(channel)
        with nogil:
            check(self.__backend.output(ctxt.get(), c_channel, c_samples))
