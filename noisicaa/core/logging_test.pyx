from cpython.ref cimport PyObject
from libcpp.memory cimport unique_ptr

from .logging cimport *
from .logging import *

import unittest


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
