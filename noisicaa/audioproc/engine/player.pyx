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

from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem


cdef class PyPlayer(object):
    def __init__(self, PyHostSystem host_system, str realm):
        self.__realm = realm

        self.__player_ptr.reset(new Player(realm.encode('utf-8'), host_system.get()))
        self.__player = self.__player_ptr.get()

    cdef Player* get(self) nogil:
        return self.__player

    cdef Player* release(self) nogil:
        return self.__player_ptr.release()

    def cleanup(self):
        self.__player_ptr.reset()
        self.__player = NULL

    def update_state(self, state):
        self.__player.update_state(state.SerializeToString())
