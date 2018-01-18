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
from unittest import mock

from noisidev import unittest
from noisicaa import audioproc
from noisicaa.node_db.private import db as node_db

from . import project
from . import sample_track


TESTDATA = os.path.abspath(os.path.join(os.path.dirname(__file__), 'testdata'))


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]


class ControlTrackConnectorTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = project.BaseProject.make_demo(node_db=self.node_db)
        self.track = sample_track.SampleTrack(name='test')
        self.project.master_group.tracks.append(self.track)

        self.sample1 = sample_track.Sample(path=os.path.join(TESTDATA, 'future-thunder1.wav'))
        self.project.samples.append(self.sample1)
        self.sample2 = sample_track.Sample(path=os.path.join(TESTDATA, 'kick-gettinglaid.wav'))
        self.project.samples.append(self.sample2)

        self.messages = []

        self.player = mock.Mock()
        def send_node_message(node_id, msg):
            self.assertEqual(node_id, self.track.sample_script_name)
            # TODO: track the messages themselves and inspect their contents as well.
            self.messages.append(msg.WhichOneof('msg'))
        self.player.send_node_message.side_effect = send_node_message

    async def cleanup_testcase(self):
        await self.node_db.cleanup()

    def test_messages_on_mutations(self):
        connector = self.track.create_player_connector(self.player)
        try:
            self.messages.clear()
            self.track.samples.insert(
                0,
                sample_track.SampleRef(
                    time=audioproc.MusicalTime(1, 4), sample_id=self.sample1.id))
            self.assertEqual(
                self.messages,
                ['sample_script_add_sample'])

            self.messages.clear()
            self.track.samples.insert(
                1,
                sample_track.SampleRef(
                    time=audioproc.MusicalTime(2, 4), sample_id=self.sample2.id))
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
            self.track.samples[0].sample_id = self.sample1.id
            self.assertEqual(
                self.messages,
                ['sample_script_remove_sample',
                 'sample_script_add_sample'])

        finally:
            connector.close()

    def test_messages_on_init(self):
        self.track.samples.insert(
            0,
            sample_track.SampleRef(time=audioproc.MusicalTime(1, 4), sample_id=self.sample1.id))
        self.track.samples.insert(
            1,
            sample_track.SampleRef(time=audioproc.MusicalTime(2, 4), sample_id=self.sample2.id))

        connector = self.track.create_player_connector(self.player)
        try:
            self.assertEqual(
                self.messages,
                ['sample_script_add_sample',
                 'sample_script_add_sample'])

        finally:
            connector.close()
