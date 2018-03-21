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

from noisicaa import core
from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from noisicaa.audioproc.public import player_state_pb2


cdef class PyPlayer(object):
    def __init__(self, PyHostSystem host_system):
        self.listeners = core.CallbackRegistry()
        self.__player_ptr.reset(new Player(host_system.get(), self._state_callback, <PyObject*>self))
        self.__player = self.__player_ptr.get()

    cdef Player* get(self) nogil:
        return self.__player

    cdef Player* release(self) nogil:
        return self.__player_ptr.release()

    def setup(self):
        with nogil:
            check(self.__player.setup())

    def cleanup(self):
        # Only do cleanup, when we still own the player.
        cdef Player* player = self.__player_ptr.get()
        if player != NULL:
            with nogil:
                player.cleanup()

    def update_state(self, state):
        self.__player.update_state(state.SerializeToString())

    @staticmethod
    cdef void _state_callback(void* c_self, const string& state_serialized) with gil:
        cdef PyPlayer self = <object><PyObject*>c_self

        # Have to stash away any active exception, because otherwise exception handling
        # might get confused.
        # See https://github.com/cython/cython/issues/1877
        cdef PyObject* exc_type
        cdef PyObject* exc_value
        cdef PyObject* exc_trackback
        PyErr_Fetch(&exc_type, &exc_value, &exc_trackback)
        try:
            state_pb = player_state_pb2.PlayerState()
            state_pb.ParseFromString(state_serialized)
            self.listeners.call('player_state', state_pb)

        finally:
            PyErr_Restore(exc_type, exc_value, exc_trackback)

