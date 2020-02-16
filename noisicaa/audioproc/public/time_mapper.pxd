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

from libc.stdint cimport uint32_t, uint64_t
from libcpp cimport bool
from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport Status
from .musical_time cimport MusicalTime, MusicalDuration


cdef extern from "noisicaa/audioproc/public/time_mapper.h" namespace "noisicaa" nogil:
    cppclass TimeMapper:
        TimeMapper()  # only declared, because otherwise cython complains when instanciating
                      # a TimeMapper.iterator on the stack. cython bug?
        TimeMapper(uint32_t sample_rate)

        Status setup()
        void cleanup()

        uint32_t sample_rate() const

        void set_bpm(uint32_t bpm)
        uint32_t bpm() const

        void set_duration(MusicalDuration duration)
        MusicalDuration duration() const
        MusicalTime end_time() const
        uint64_t num_samples() const

        MusicalTime sample_to_musical_time(uint64_t sample_time) const
        uint64_t musical_to_sample_time(MusicalTime musical_time) const

        cppclass iterator:
            iterator& operator++()
            iterator operator++(int)
            bool operator==(iterator other) const
            bool operator!=(iterator other) const
            MusicalTime operator*() const

        iterator begin()
        iterator find(MusicalTime t)


cdef class PyTimeMapper(object):
    cdef unique_ptr[TimeMapper] __ptr
    cdef TimeMapper* __tmap
    cdef dict __listeners

    cdef TimeMapper* get(self)
    cdef TimeMapper* release(self)
