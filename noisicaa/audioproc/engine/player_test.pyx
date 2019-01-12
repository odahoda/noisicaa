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

from noisidev import unittest
from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from .player cimport Player


cdef class PlayerTestMixin(object):
    cdef PyHostSystem host_system

    def setup_testcase(self):
        self.host_system = PyHostSystem()
        self.host_system.setup()

    def cleanup_testcase(self):
        self.host_system.cleanup()

    # def test_state(self):
    #     cdef Player* player = new Player(self.host_system.get(), NULL, NULL)
    #     try:
    #         check(player.setup())

    #         self.assertFalse(player.playing())
    #         player.start()
    #         self.assertTrue(player.playing())
    #         player.stop()
    #         self.assertFalse(player.playing())

    #         self.assertFalse(player.loop_enabled())
    #         player.set_loop_enabled(True)
    #         self.assertTrue(player.loop_enabled())
    #         player.set_loop_enabled(False)
    #         self.assertFalse(player.loop_enabled())

    #         self.assertTrue(player.loop_start_time() < MusicalTime(0, 1))
    #         player.set_loop_start_time(MusicalTime(2, 3))
    #         self.assertTrue(player.loop_start_time() == MusicalTime(2, 3))

    #         self.assertTrue(player.loop_end_time() < MusicalTime(0, 1))
    #         player.set_loop_end_time(MusicalTime(2, 3))
    #         self.assertTrue(player.loop_end_time() == MusicalTime(2, 3))

    #     finally:
    #         with nogil:
    #             player.cleanup()
    #         del player


class PlayerTest(PlayerTestMixin, unittest.TestCase):
    pass
