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

from cpython.ref cimport PyObject
from cpython.exc cimport PyErr_Fetch, PyErr_Restore
from cython.operator cimport dereference, preincrement
from noisicaa.core.status cimport check
from .musical_time cimport PyMusicalTime, PyMusicalDuration


cdef class PyTimeMapper(object):
    def __init__(self, sample_rate):
        self.__ptr.reset(new TimeMapper(sample_rate))
        self.__tmap = self.__ptr.get()
        self.__listeners = {}
        self.__project = None

    def setup(self, project=None):
        with nogil:
            check(self.__tmap.setup())

        if project is not None:
            self.__project = project

            self.bpm = self.__project.bpm
            self.__listeners['bpm'] = self.__project.bpm_changed.add(self.__on_bpm_changed)

            self.duration = self.__project.duration
            self.__listeners['duration'] = self.__project.duration_changed.add(self.__on_duration_changed)

        self.__tmap.set_change_callback(self.__change_callback, <PyObject*>self)

    def cleanup(self):
        self.__project = None

        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        self.__tmap.cleanup()

    cdef TimeMapper* get(self):
        return self.__tmap

    cdef TimeMapper* release(self):
        return self.__ptr.release()

    @staticmethod
    cdef void __change_callback(void* c_self) with gil:
        self = <PyTimeMapper><PyObject*>c_self

        # Have to stash away any active exception, because otherwise exception handling
        # might get confused.
        # See https://github.com/cython/cython/issues/1877
        cdef PyObject* exc_type
        cdef PyObject* exc_value
        cdef PyObject* exc_trackback
        PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)
        try:
            if self.__project is not None:
                self.__project.time_mapper_changed.call()

        finally:
            PyErr_Restore(exc_type, exc_value, exc_trackback)


    def __on_bpm_changed(self, change):
        self.bpm = change.new_value

    def __on_duration_changed(self, change):
        self.duration = change.new_value

    @property
    def sample_rate(self):
        return int(self.__tmap.sample_rate())

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
        assert value is not None
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

