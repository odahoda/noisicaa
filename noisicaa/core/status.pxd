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

from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "noisicaa/core/status.h" namespace "noisicaa" nogil:
    cppclass Status:
        const char* file() const
        int line() const
        bool is_error() const
        bool is_connection_closed() const
        bool is_timeout() const
        bool is_os_error() const
        string message() const

        @staticmethod
        Status Ok()

        @staticmethod
        Status Error(const string& message)

    cppclass StatusOr[T](Status):
        T result() const

cdef int check(const Status& status) nogil except -1

