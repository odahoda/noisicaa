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

from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore
from libc.stdio cimport fprintf, stderr
import logging

cdef void pylogging_cb(
    void* handle, const char* c_logger_name, LogLevel c_level, const char* c_msg) with gil:
    # Have to stash away any active exception, because otherwise exception handling
    # might get confused.
    # See https://github.com/cython/cython/issues/1877
    cdef PyObject* exc_type
    cdef PyObject* exc_value
    cdef PyObject* exc_trackback
    PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)

    try:
        logger_name = bytes(c_logger_name).decode('utf-8')
        level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            }[c_level]
        msg = bytes(c_msg).decode('utf-8')

        logger = logging.getLogger(logger_name)
        logger.log(level, msg)
    except:
        fprintf(stderr, "Failed to log message %s\n", c_msg);

    PyErr_Restore(exc_type, exc_value, exc_trackback)


def init_pylogging():
    cdef LogSink* sink = new PyLogSink(NULL, pylogging_cb)
    LoggerRegistry.get_registry().set_sink(sink)
