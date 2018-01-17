#!/usr/bin/python3

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

import fractions

cimport cython

from . import musical_time_pb2


cdef Fraction _as_fraction(v) except *:
    if isinstance(v, PyMusicalDuration):
        return (<PyMusicalDuration>v)._duration
    elif isinstance(v, PyMusicalTime):
        return (<PyMusicalTime>v)._time
    elif isinstance(v, fractions.Fraction):
        return Fraction(v.numerator, v.denominator)
    elif isinstance(v, int):
        return Fraction(v, 1)
    else:
        raise TypeError("%s (%s)" % (v, type(v)))


@cython.auto_pickle(False)
cdef class PyMusicalDuration(object):
    def __init__(self, *args):
        if len(args) == 0:
            self._duration = MusicalDuration()
        elif len(args) == 2:
            self._duration = MusicalDuration(<int>args[0], <int>args[1])
        elif len(args) == 1:
            if isinstance(args[0], PyMusicalDuration):
                self._duration = (<PyMusicalDuration>args[0])._duration
            elif isinstance(args[0], fractions.Fraction):
                self._duration = MusicalDuration(<int>args[0].numerator, <int>args[0].denominator)
            elif isinstance(args[0], int):
                self._duration = MusicalDuration(<int>args[0])
            else:
                raise TypeError(repr(args[0]))
        else:
            raise TypeError(repr(args))

    @staticmethod
    cdef PyMusicalDuration create(MusicalDuration d):
        cdef PyMusicalDuration obj = PyMusicalDuration.__new__(PyMusicalDuration)
        obj._duration = d
        return obj

    cdef MusicalDuration get(PyMusicalDuration self):
        return self._duration

    def __hash__(self):
        return hash((self.numerator, self.denominator))

    def __str__(self):
        return 'MusicalDuration(%d, %d)' % (self.numerator, self.denominator)

    def __repr__(self):
        return str(self)

    def __getstate__(PyMusicalDuration self):
        return (int(self._duration.numerator()), int(self._duration.denominator()))

    def __setstate__(PyMusicalDuration self, state):
        self._duration = MusicalDuration(state[0], state[1])

    @property
    def numerator(PyMusicalDuration self):
        return int(self._duration.numerator())

    @property
    def denominator(PyMusicalDuration self):
        return int(self._duration.denominator())

    @property
    def fraction(self):
        return fractions.Fraction(self.numerator, self.denominator)

    def to_float(self):
        return float(self._duration.to_float())

    def __bool__(PyMusicalDuration self):
        return self._duration != MusicalDuration(0, 1)

    def __eq__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration == other._duration

    def __ne__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration != other._duration

    def __gt__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration > other._duration

    def __ge__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration >= other._duration

    def __le__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration <= other._duration

    def __lt__(PyMusicalDuration self, PyMusicalDuration other):
        return self._duration < other._duration

    def __add__(PyMusicalDuration self, PyMusicalDuration other):
        return PyMusicalDuration.create(self._duration + other._duration)

    def __sub__(PyMusicalDuration self, PyMusicalDuration other):
        return PyMusicalDuration.create(self._duration - other._duration)

    def __mul__(PyMusicalDuration self, other):
        return PyMusicalDuration.create(self._duration * _as_fraction(other))

    def __truediv__(PyMusicalDuration self, other):
        # return PyMusicalDuration.create(self._duration / _as_fraction(other))
        # generates incorrect code. cython bug?
        cdef MusicalDuration v = self._duration
        v /= _as_fraction(other)
        return PyMusicalDuration.create(v)

    @classmethod
    def from_proto(cls, pb):
        return cls(pb.numerator, pb.denominator)

    def to_proto(self):
        return musical_time_pb2.MusicalDuration(
            numerator=self.numerator,
            denominator=self.denominator,
        )


@cython.auto_pickle(False)
cdef class PyMusicalTime(object):
    def __init__(self, *args):
        if len(args) == 0:
            self._time = MusicalTime()
        elif len(args) == 2:
            self._time = MusicalTime(<int>args[0], <int>args[1])
        elif len(args) == 1:
            if isinstance(args[0], PyMusicalTime):
                self._time = (<PyMusicalTime>args[0])._time
            elif isinstance(args[0], fractions.Fraction):
                self._time = MusicalTime(<int>args[0].numerator, <int>args[0].denominator)
            elif isinstance(args[0], int):
                self._time = MusicalTime(<int>args[0])
            else:
                raise TypeError(repr(args[0]))
        else:
            raise TypeError(repr(args))

    @staticmethod
    cdef PyMusicalTime create(MusicalTime t):
        cdef PyMusicalTime obj = PyMusicalTime.__new__(PyMusicalTime)
        obj._time = t
        return obj

    cdef MusicalTime get(self):
        return self._time

    def __hash__(self):
        return hash((self.numerator, self.denominator))

    def __str__(self):
        return 'MusicalTime(%d, %d)' % (self.numerator, self.denominator)

    def __repr__(self):
        return str(self)

    def __getstate__(PyMusicalTime self):
        return (int(self._time.numerator()), int(self._time.denominator()))

    def __setstate__(PyMusicalTime self, state):
        self._time = MusicalTime(state[0], state[1])

    @property
    def numerator(self):
        return int(self._time.numerator())

    @property
    def denominator(self):
        return int(self._time.denominator())

    @property
    def fraction(self):
        return fractions.Fraction(self.numerator, self.denominator)

    def to_float(self):
        return float(self._duration.to_float())

    def __bool__(PyMusicalTime self):
        return self._time != MusicalTime(0, 1)

    def __eq__(PyMusicalTime self, PyMusicalTime other):
        return self._time == other._time

    def __ne__(PyMusicalTime self, PyMusicalTime other):
        return self._time != other._time

    def __gt__(PyMusicalTime self, PyMusicalTime other):
        return self._time > other._time

    def __ge__(PyMusicalTime self, PyMusicalTime other):
        return self._time >= other._time

    def __le__(PyMusicalTime self, PyMusicalTime other):
        return self._time <= other._time

    def __lt__(PyMusicalTime self, PyMusicalTime other):
        return self._time < other._time

    def __add__(PyMusicalTime self, PyMusicalDuration other):
        return PyMusicalTime.create(self._time + other._duration)

    def __sub__(PyMusicalTime self, other):
        if isinstance(other, PyMusicalDuration):
            return PyMusicalTime.create(self._time - (<PyMusicalDuration>other)._duration)
        elif isinstance(other, PyMusicalTime):
            return PyMusicalDuration.create(self._time - (<PyMusicalTime>other)._time)
        return TypeError(repr(other))

    def __mul__(PyMusicalTime self, other):
        return PyMusicalTime.create(self._time * _as_fraction(other))

    def __truediv__(PyMusicalTime self, other):
        # return PyMusicalTime.create(self._time / _as_fraction(other))
        # generates incorrect code. cython bug?
        cdef MusicalTime v = self._time
        v /= _as_fraction(other)
        return PyMusicalTime.create(v)

    @classmethod
    def from_proto(cls, pb):
        return cls(pb.numerator, pb.denominator)

    def to_proto(self):
        return musical_time_pb2.MusicalTime(
            numerator=self.numerator,
            denominator=self.denominator,
        )
