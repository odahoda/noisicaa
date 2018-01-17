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

from libc.stdint cimport int64_t
from libcpp cimport bool

cdef extern from "noisicaa/audioproc/vm/musical_time.h" namespace "noisicaa" nogil:
    cppclass Fraction:
        Fraction()
        Fraction(int64_t n, int64_t d)
        Fraction(const Fraction& t)

        int64_t numerator() const
        int64_t denominator() const
        float to_float() const
        double to_double() const

    cppclass MusicalDuration(Fraction):
        MusicalDuration()
        MusicalDuration(int64_t n)
        MusicalDuration(int64_t n, int64_t d)
        MusicalDuration(const MusicalDuration& t)

        void set(const MusicalDuration& t)
        void add(const MusicalDuration& t)
        void sub(const MusicalDuration& t)
        void mul(const Fraction& t)
        void div(const Fraction& t)

        # Actual implementation in C++ have different signatures, which
        # Cython does not understand. But it is sufficient that Cython
        # knows that these operators exist.
        MusicalDuration operator+(const MusicalDuration& b)
        MusicalDuration operator-(const MusicalDuration& b)
        MusicalDuration operator*(const Fraction& b)
        MusicalDuration operator/(const Fraction& b)
        bool operator==(const MusicalDuration& b)
        bool operator!=(const MusicalDuration& b)
        bool operator<(const MusicalDuration& b)
        bool operator>(const MusicalDuration& b)
        bool operator<=(const MusicalDuration& b)
        bool operator>=(const MusicalDuration& b)

    cppclass MusicalTime(Fraction):
        MusicalTime()
        MusicalTime(int64_t n)
        MusicalTime(int64_t n, int64_t d)
        MusicalTime(const MusicalTime& t)

        void set(const MusicalTime& t)
        void add(const MusicalDuration& t)
        void sub(const MusicalDuration& t)
        void mul(const Fraction& t)
        void div(const Fraction& t)

        # Actual implementation in C++ have different signatures, which
        # Cython does not understand. But it is sufficient that Cython
        # knows that these operators exist.
        MusicalTime operator+(const MusicalDuration& b)
        MusicalTime operator-(const MusicalDuration& b)
        MusicalDuration operator-(const MusicalTime& b)
        MusicalTime operator*(const Fraction& b)
        MusicalTime operator/(const Fraction& b)
        bool operator==(const MusicalTime& b)
        bool operator!=(const MusicalTime& b)
        bool operator<(const MusicalTime& b)
        bool operator>(const MusicalTime& b)
        bool operator<=(const MusicalTime& b)
        bool operator>=(const MusicalTime& b)


cdef class PyMusicalDuration(object):
    cdef MusicalDuration _duration

    @staticmethod
    cdef PyMusicalDuration create(MusicalDuration d)
    cdef MusicalDuration get(self)


cdef class PyMusicalTime(object):
    cdef MusicalTime _time

    @staticmethod
    cdef PyMusicalTime create(MusicalTime d)
    cdef MusicalTime get(self)
