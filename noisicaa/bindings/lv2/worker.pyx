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
        logger.info("schedule_work(%d, %d)", size, <int>data)
        return LV2_WORKER_ERR_UNKNOWN
