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

cdef extern from "noisicaa/core/logging.h" namespace "noisicaa" nogil:
    enum LogLevel:
        DEBUG
        INFO
        WARNING
        ERROR

    cppclass LoggerRegistry

    cppclass Logger:
        Logger(const char* name, LoggerRegistry* registry)
        void log(LogLevel level, const char* fmt, ...)
        void debug(const char* fmt, ...)
        void info(const char* fmt, ...)
        void warning(const char* fmt, ...)
        void error(const char* fmt, ...)

    cppclass LogSink:
        void emit(const char* logger, LogLevel level, const char* msg)

    cppclass PyLogSink(LogSink):
        ctypedef void (*callback_t)(void*, const char*, LogLevel, const char*)

        PyLogSink(void* handle, callback_t callback)
        void emit(const char* logger, LogLevel level, const char* msg)

    cppclass LoggerRegistry:
        @staticmethod
        LoggerRegistry* get_registry()
        @staticmethod
        Logger* get_logger(const char* name)

        void set_sink(LogSink* sink)
