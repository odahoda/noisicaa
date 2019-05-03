#!/usr/bin/python3

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
from noisicaa import audioproc
from noisicaa.music import base_track_test
from . import model
from . import commands


class ControlTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://control-track'
    track_cls = model.ControlTrack

    async def test_add_control_point(self):
        track = await self._add_track()

        await self.client.send_command(commands.create_control_point(
            track,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))
        point = track.points[-1]
        self.assertEqual(len(track.points), 1)
        self.assertIs(track.points[0], point)
        self.assertEqual(point.time, audioproc.MusicalTime(1, 4))
        self.assertAlmostEqual(point.value, 0.7)

    async def test_delete_control_point(self):
        track = await self._add_track()
        await self.client.send_command(commands.create_control_point(
            track,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))
        point = track.points[-1]

        await self.client.send_command(commands.delete_control_point(point))
        self.assertEqual(len(track.points), 0)

    async def test_control_point_set_time(self):
        track = await self._add_track()
        await self.client.send_command(commands.create_control_point(
            track,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))
        point = track.points[-1]

        await self.client.send_command(commands.update_control_point(
            point,
            set_time=audioproc.MusicalTime(3, 4)))
        self.assertEqual(point.time, audioproc.MusicalTime(3, 4))

    async def test_control_point_set_value(self):
        track = await self._add_track()
        await self.client.send_command(commands.create_control_point(
            track,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))
        point = track.points[-1]

        await self.client.send_command(commands.update_control_point(
            point,
            set_value=0.6))
        self.assertAlmostEqual(point.value, 0.6)
