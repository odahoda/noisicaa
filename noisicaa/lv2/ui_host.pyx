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

import logging
import traceback

from cpython.ref cimport PyObject

from noisicaa.core.status cimport check

logger = logging.getLogger(__name__)


cdef class PyLV2UIHost(object):
    def __init__(self, desc, host_system, control_value_change_cb):
        self.__desc = desc
        self.__host_system = host_system
        self.__control_value_change_cb = control_value_change_cb

        self.__ptr.reset(new LV2UIHost(
            self.__desc.SerializeToString(),
            self.__host_system.get(),
            <PyObject*>self, self.control_value_change))
        self.__host = self.__ptr.get()

    cdef LV2UIHost* get(self):
        return self.__host

    cdef LV2UIHost* release(self):
        return self.__ptr.release()

    @staticmethod
    cdef void control_value_change(void* handle, uint32_t port_index, float value) with gil:
        cdef PyLV2UIHost self = <object>handle
        try:
            self.__control_value_change_cb(port_index, value)

        except Exception as exc:
            logger.exception("Callback failed with an exception: %s", exc)

    def setup(self):
        with nogil:
            check(self.__host.setup())

    def cleanup(self):
        with nogil:
            self.__host.cleanup()

    @property
    def wid(self):
        return self.__host.wid()

    @property
    def size(self):
        return (self.__host.width(), self.__host.height())
