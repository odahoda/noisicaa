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
from . import client_impl
from . import commands


class ControlTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://control-track'
    track_cls = client_impl.ControlTrack

    async def test_add_control_point(self):
        track = await self._add_track()

        await self.client.send_command(commands.add_control_point(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))
        self.assertEqual(track.points[0].time, audioproc.MusicalTime(1, 4))
        self.assertAlmostEqual(track.points[0].value, 0.7)

    async def test_remove_control_point(self):
        track = await self._add_track()
        await self.client.send_command(commands.add_control_point(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))

        await self.client.send_command(commands.remove_control_point(
            track.id,
            point_id=track.points[0].id))
        self.assertEqual(len(track.points), 0)

    async def test_move_control_point(self):
        track = await self._add_track()
        await self.client.send_command(commands.add_control_point(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            value=0.7))

        await self.client.send_command(commands.move_control_point(
            track.id,
            point_id=track.points[0].id,
            time=audioproc.MusicalTime(3, 4),
            value=0.6))
        self.assertEqual(track.points[0].time, audioproc.MusicalTime(3, 4))
        self.assertAlmostEqual(track.points[0].value, 0.6)
