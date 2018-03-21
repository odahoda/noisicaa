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

from cython.operator cimport dereference, preincrement
from noisicaa.core.status cimport check
from .musical_time cimport PyMusicalTime, PyMusicalDuration


cdef class PyTimeMapper(object):
    def __init__(self, sample_rate):
        self.__ptr.reset(new TimeMapper(sample_rate))
        self.__tmap = self.__ptr.get()
        self.__listeners = {}

    def setup(self, project=None):
        with nogil:
            check(self.__tmap.setup())

        if project is not None:
            self.bpm = project.bpm
            self.__listeners['bpm'] = project.listeners.add('bpm', self.__on_bpm_changed)

            self.duration = project.duration
            self.__listeners['duration'] = project.listeners.add(
                'duration', self.__on_duration_changed)

    def cleanup(self):
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        self.__tmap.cleanup()

    cdef TimeMapper* get(self):
        return self.__tmap

    cdef TimeMapper* release(self):
        return self.__ptr.release()

    def __on_bpm_changed(self, old_value, new_value):
        self.bpm = new_value

    def __on_duration_changed(self, old_value, new_value):
        self.duration = new_value

    @property
    def bpm(self):
        return int(self.__tmap.bpm())

    @bpm.setter
    def bpm(self, value):
        self.__tmap.set_bpm(value)

    @property
    def duration(self):
        return PyMusicalDuration.create(self.__tmap.duration())

    @duration.setter
    def duration(self, PyMusicalDuration value):
        self.__tmap.set_duration(value.get())

    @property
    def end_time(self):
        return PyMusicalTime.create(self.__tmap.end_time())

    @property
    def num_samples(self):
        return int(self.__tmap.num_samples())

    def sample_to_musical_time(self, uint64_t sample_time):
        return PyMusicalTime.create(self.__tmap.sample_to_musical_time(sample_time))

    def musical_to_sample_time(self, PyMusicalTime musical_time):
        return int(self.__tmap.musical_to_sample_time(musical_time.get()))

    def __iter__(self):
        cdef TimeMapper.iterator it = self.__tmap.begin()
        while True:
            yield PyMusicalTime.create(dereference(it))
            preincrement(it)

    def find(self, PyMusicalTime t):
        cdef TimeMapper.iterator it = self.__tmap.find(t.get())
        while True:
            yield PyMusicalTime.create(dereference(it))
            preincrement(it)

