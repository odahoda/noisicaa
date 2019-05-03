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

import os.path

from noisidev import unittest
from noisicaa import audioproc
#from noisicaa.core import proto_types_pb2
from noisicaa.music import base_track_test
#from . import ipc_pb2
from . import model
from . import commands


class SampleTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://sample-track'
    track_cls = model.SampleTrack

    async def test_create_sample(self):
        track = await self._add_track()

        await self.client.send_command(commands.create_sample(
            track,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(1, 4))

    async def test_delete_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands.create_sample(
            track,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

        await self.client.send_command(commands.delete_sample(
            track.samples[0]))
        self.assertEqual(len(track.samples), 0)

    async def test_sample_set_time(self):
        track = await self._add_track()
        await self.client.send_command(commands.create_sample(
            track,
            time=audioproc.MusicalTime(1, 4),
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

        await self.client.send_command(commands.update_sample(
            track.samples[0],
            set_time=audioproc.MusicalTime(3, 4)))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(3, 4))

    # TODO: fix
    # async def test_render_sample(self):
    #     track = await self._add_track()
    #     await self.client.send_command(commands.create_sample(
    #         track,
    #         time=audioproc.MusicalTime(1, 4),
    #         path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav')))

    #     request = ipc_pb2.RenderSampleRequest(
    #         sample_id=track.samples[0].id,
    #         scale_x=proto_types_pb2.Fraction(numerator=100, denominator=1))
    #     response = ipc_pb2.RenderSampleResponse()
    #     await self.client.call('SAMPLE_TRACK_RENDER_SAMPLE', request, response)
    #     self.assertFalse(response.broken)
    #     self.assertGreater(len(response.rms), 0)
