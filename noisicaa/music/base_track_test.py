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

import logging

from noisidev import unittest
from . import commands_pb2
from . import commands_test

logger = logging.getLogger(__name__)


class BaseTrackTest(commands_test.CommandsTestBase):
    async def test_move_track(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track1 = self.project.master_group.tracks[0]
        track2 = self.project.master_group.tracks[1]

        await self.client.send_command(commands_pb2.Command(
            target=track1.id,
            move_track=commands_pb2.MoveTrack(
                direction=1)))
        self.assertEqual(track1.index, 1)
        self.assertEqual(track2.index, 0)

    async def test_reparent_track(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='group',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]
        grp = self.project.master_group.tracks[1]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            reparent_track=commands_pb2.ReparentTrack(
                new_parent=grp.id,
                index=0)))
        self.assertEqual(len(self.project.master_group.tracks), 1)
        self.assertEqual(len(grp.tracks), 1)
        self.assertIs(track.parent, grp)

    async def test_update_track_properties_name(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                name='Lead')))
        self.assertEqual(track.name, 'Lead')

    async def test_update_track_properties_visible(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                visible=False)))
        self.assertFalse(track.visible)

    @unittest.skip("Implementation broken")
    async def test_update_track_properties_muted(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                muted=True)))
        self.assertTrue(track.muted)

    @unittest.skip("Implementation broken")
    async def test_update_track_properties_gain(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                gain=-4.0)))
        self.assertAlmostEqual(track.gain, -4.0)

    @unittest.skip("Implementation broken")
    async def test_update_track_properties_pan(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                pan=-0.7)))
        self.assertAlmostEqual(track.pan, -0.7)

    async def test_update_track_properties_transport_octaves(self):
        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=self.project.master_group.id)))
        track = self.project.master_group.tracks[0]

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                transpose_octaves=1)))
        self.assertEqual(track.transpose_octaves, 1)
