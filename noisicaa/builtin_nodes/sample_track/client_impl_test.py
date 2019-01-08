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
import os.path

from noisidev import unittest
from noisicaa import audioproc
from noisicaa.music import base_track_test
from . import client_impl
from . import commands


class SampleTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://sample-track'
    track_cls = client_impl.SampleTrack

    async def test_add_sample(self):
        track = await self._add_track()

        await self.client.send_command(commands.add_sample(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(1, 4))

    async def test_remove_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands.add_sample(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

        await self.client.send_command(commands.remove_sample(
            track.id,
            sample_id=track.samples[0].id))
        self.assertEqual(len(track.samples), 0)

    async def test_move_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands.add_sample(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

        await self.client.send_command(commands.move_sample(
            track.id,
            sample_id=track.samples[0].id,
            time=audioproc.MusicalTime(3, 4)))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(3, 4))

    async def test_render_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands.add_sample(
            track.id,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

        samples = await self.client.send_command(commands.render_sample(
            track.samples[0].id,
            scale_x=fractions.Fraction(100, 1)))
        self.assertEqual(samples[0], 'rms')
