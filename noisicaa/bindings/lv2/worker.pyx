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

from cpython.ref cimport PyObject
from libc.stdint cimport uint32_t
from libc cimport stdlib
from libc cimport string
cimport numpy

import contextlib
import logging
import operator
import numpy

logger = logging.getLogger(__name__)


cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


cdef class Worker_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/worker#schedule'

    def __cinit__(self):
        self.data.handle = <PyObject*>self
        self.data.schedule_work = self.schedule_work

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_Worker_Status schedule_work(
        LV2_Worker_Schedule_Handle handle, uint32_t size, const void* data):
        cdef Worker_Feature self = <Worker_Feature>handle
        logger.info("schedule_work(%d, %d)", size, <long>data)
        return LV2_WORKER_ERR_UNKNOWN
