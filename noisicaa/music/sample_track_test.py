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

import os.path
from typing import List  # pylint: disable=unused-import

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisicaa import audioproc
from noisicaa.model import project_pb2
from . import project
from . import sample_track
from . import commands_test
from . import commands_pb2
from . import project_client

class ControlTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()

        self.project = demo_project.basic(self.pool, project.BaseProject, node_db=self.node_db)
        self.track = self.pool.create(sample_track.SampleTrack, name='test')
        self.project.master_group.tracks.append(self.track)

        self.sample1 = self.pool.create(
            sample_track.Sample,
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))
        self.project.samples.append(self.sample1)
        self.sample2 = self.pool.create(
            sample_track.Sample,
            path=os.path.join(unittest.TESTDATA_DIR, 'kick-gettinglaid.wav'))
        self.project.samples.append(self.sample2)

        self.messages = []  # type: List[str]

    def message_cb(self, msg):
        self.assertEqual(msg.node_id, self.track.sample_script_name)
        # TODO: track the messages themselves and inspect their contents as well.
        self.messages.append(msg.WhichOneof('msg'))

    def test_messages_on_mutations(self):
        connector = self.track.create_track_connector(message_cb=self.message_cb)
        try:
            self.assertEqual(connector.init(), [])

            self.messages.clear()
            self.track.samples.insert(
                0,
                self.pool.create(
                    sample_track.SampleRef,
                    time=audioproc.MusicalTime(1, 4), sample=self.sample1))
            self.assertEqual(
                self.messages,
                ['sample_script_add_sample'])

            self.messages.clear()
            self.track.samples.insert(
                1,
                self.pool.create(
                    sample_track.SampleRef,
                    time=audioproc.MusicalTime(2, 4), sample=self.sample2))
            self.assertEqual(
                self.messages,
                ['sample_script_add_sample'])

            self.messages.clear()
            del self.track.samples[0]
            self.assertEqual(
                self.messages,
                ['sample_script_remove_sample'])

            self.messages.clear()
            self.track.samples[0].time = audioproc.MusicalTime(3, 4)
            self.assertEqual(
                self.messages,
                ['sample_script_remove_sample',
                 'sample_script_add_sample'])

            self.messages.clear()
            self.track.samples[0].sample = self.sample1
            self.assertEqual(
                self.messages,
                ['sample_script_remove_sample',
                 'sample_script_add_sample'])

        finally:
            connector.close()

    def test_messages_on_init(self):
        self.track.samples.insert(
            0,
            self.pool.create(
                sample_track.SampleRef,
                time=audioproc.MusicalTime(1, 4), sample=self.sample1))
        self.track.samples.insert(
            1,
            self.pool.create(
                sample_track.SampleRef,
                time=audioproc.MusicalTime(2, 4), sample=self.sample2))

        connector = self.track.create_track_connector(message_cb=self.message_cb)
        try:
            messages = connector.init()

            self.assertEqual(
                [msg.WhichOneof('msg') for msg in messages],
                ['sample_script_add_sample',
                 'sample_script_add_sample'])

        finally:
            connector.close()


class SampleTrackTest(commands_test.CommandsTestBase):
    async def test_add_remove(self):
        insert_index = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='sample',
                parent_group_id=self.project.master_group.id)))
        self.assertEqual(insert_index, 0)

        track = self.project.master_group.tracks[insert_index]
        self.assertIsInstance(track, project_client.SampleTrack)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            remove_track=commands_pb2.RemoveTrack(
                track_id=track.id)))
        self.assertEqual(len(self.project.master_group.tracks), 0)

    async def _add_track(self):
        insert_index = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='sample',
                parent_group_id=self.project.master_group.id)))
        return self.project.master_group.tracks[insert_index]

    async def test_add_sample(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_sample=commands_pb2.AddSample(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(1, 4))

    async def test_remove_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_sample=commands_pb2.AddSample(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))))

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            remove_sample=commands_pb2.RemoveSample(
                sample_id=track.samples[0].id)))
        self.assertEqual(len(track.samples), 0)

    async def test_move_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_sample=commands_pb2.AddSample(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))))

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            move_sample=commands_pb2.MoveSample(
                sample_id=track.samples[0].id,
                time=audioproc.MusicalTime(3, 4).to_proto())))
        self.assertEqual(track.samples[0].time, audioproc.MusicalTime(3, 4))

    async def test_render_sample(self):
        track = await self._add_track()
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_sample=commands_pb2.AddSample(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))))

        samples = await self.client.send_command(commands_pb2.Command(
            target=track.samples[0].id,
            render_sample=commands_pb2.RenderSample(
                scale_x=project_pb2.Fraction(numerator=100, denominator=1))))
        self.assertEqual(samples[0], 'rms')
