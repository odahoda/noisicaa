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

import logging

from noisicaa.core.status cimport check

logger = logging.getLogger(__name__)


cdef class PyPluginUIHost(object):

    cdef int init(self, PluginUIHost* plugin_ui_host) except -1:
        self.__plugin_ui_host_ptr.reset(plugin_ui_host)
        self.__plugin_ui_host = plugin_ui_host

    cdef PluginUIHost* get(self) nogil:
        return self.__plugin_ui_host

    cdef PluginUIHost* release(self) nogil:
        return self.__plugin_ui_host_ptr.release()

    def setup(self):
        with nogil:
            check(self.__plugin_ui_host.setup())

    def cleanup(self):
        # Only do cleanup, when we still own the processor.
        cdef PluginUIHost* plugin_ui_host = self.__plugin_ui_host_ptr.get()
        if plugin_ui_host != NULL:
            with nogil:
                plugin_ui_host.cleanup()

    @staticmethod
    cdef void __control_value_change(
        void* handle, uint32_t port_index, float value, uint32_t generation) with gil:
        cdef PyPluginUIHost self = <object>handle
        try:
            self.__control_value_change_cb(port_index, value, generation)

        except Exception as exc:
            logger.exception("Callback failed with an exception: %s", exc)

    @property
    def wid(self):
        return self.__plugin_ui_host.wid()

    @property
    def size(self):
        return (self.__plugin_ui_host.width(), self.__plugin_ui_host.height())
