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

import threading

from cpython.ref cimport PyObject
from libcpp.memory cimport unique_ptr

from noisidev import unittest
from .status cimport check
from .logging cimport *
from .logging import *


cdef void cb_proxy(void* handle, const char* logger, LogLevel level, const char* msg) with gil:
    cdef object handler = <object>handle
    handler(logger, level, msg)


class TestLogging(unittest.TestCase):
    def test_callback(self):
        cdef unique_ptr[LoggerRegistry] registry_ptr
        registry_ptr.reset(new LoggerRegistry())
        cdef LoggerRegistry* registry = registry_ptr.get()

        msgs = []
        def cb(logger, level, msg):
            msgs.append((logger, level, msg))

        cdef LogSink* sink = new PyLogSink(<PyObject*>cb, cb_proxy)
        registry.set_sink(sink)

        cdef unique_ptr[Logger] logger_ptr
        logger_ptr.reset(new Logger(b"noisicaa.core.logger_test.callback", registry))
        cdef Logger* logger = logger_ptr.get()

        logger.debug("debug %d", 1)
        logger.info("informational %d", 2)
        logger.warning("warning %d", 3)
        logger.error("error %d", 4)

        self.assertEqual(
            msgs,
            [(b"noisicaa.core.logger_test.callback", LogLevel.DEBUG, b"debug 1"),
             (b"noisicaa.core.logger_test.callback", LogLevel.INFO, b"informational 2"),
             (b"noisicaa.core.logger_test.callback", LogLevel.WARNING, b"warning 3"),
             (b"noisicaa.core.logger_test.callback", LogLevel.ERROR, b"error 4")])

    def test_rtsafe_sink(self):
        cdef unique_ptr[LoggerRegistry] registry_ptr
        registry_ptr.reset(new LoggerRegistry())
        cdef LoggerRegistry* registry = registry_ptr.get()

        cdef unique_ptr[Logger] logger_ptr
        logger_ptr.reset(new Logger(b"noisicaa.core.logger_test.callback", registry))
        cdef Logger* logger = logger_ptr.get()

        msgs = []
        def cb(logger, level, msg):
            msgs.append((logger, level, msg))

        def thread_main():
            cdef RTSafePyLogSink* sink
            long_string = b"a very long string" * 100
            cdef char* c_long_string = long_string
            with nogil:
                sink = new RTSafePyLogSink(<PyObject*>cb, cb_proxy)
                try:
                    check(sink.setup())
                    registry.set_threadlocal_sink(sink)

                    logger.debug("debug %d", 1)
                    logger.info("informational %d", 2)
                    logger.warning("warning %d", 3)
                    logger.error("error %d", 4)
                    logger.info(c_long_string)

                finally:
                    registry.set_threadlocal_sink(NULL)
                    sink.cleanup()
                    del sink

        thread = threading.Thread(target=thread_main)
        thread.start()
        thread.join()

        self.assertEqual(
            msgs,
            [(b"noisicaa.core.logger_test.callback", LogLevel.DEBUG, b"debug 1"),
             (b"noisicaa.core.logger_test.callback", LogLevel.INFO, b"informational 2"),
             (b"noisicaa.core.logger_test.callback", LogLevel.WARNING, b"warning 3"),
             (b"noisicaa.core.logger_test.callback", LogLevel.ERROR, b"error 4"),
             (b"noisicaa.core.logger_test.callback", LogLevel.INFO, b"a very long string" * 100)])
