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
from noisidev import demo_project
from noisicaa import audioproc
from noisicaa.node_db.private import db as node_db

from . import project
from . import sample_track


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db[uri]


class ControlTrackConnectorTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = demo_project.basic(project.BaseProject, node_db=self.node_db)
        self.track = sample_track.SampleTrack(name='test')
        self.project.master_group.tracks.append(self.track)

        self.sample1 = sample_track.Sample(
            path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))
        self.project.samples.append(self.sample1)
        self.sample2 = sample_track.Sample(
            path=os.path.join(unittest.TESTDATA_DIR, 'kick-gettinglaid.wav'))
        self.project.samples.append(self.sample2)

        self.messages = []  # type: List[str]

    def message_cb(self, msg):
        self.assertEqual(msg.node_id, self.track.sample_script_name)
        # TODO: track the messages themselves and inspect their contents as well.
        self.messages.append(msg.WhichOneof('msg'))

    async def cleanup_testcase(self):
        await self.node_db.cleanup()

    def test_messages_on_mutations(self):
        connector = self.track.create_track_connector(message_cb=self.message_cb)
        try:
            self.assertEqual(connector.init(), [])

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

        connector = self.track.create_track_connector(message_cb=self.message_cb)
        try:
            messages = connector.init()

            self.assertEqual(
                [msg.WhichOneof('msg') for msg in messages],
                ['sample_script_add_sample',
                 'sample_script_add_sample'])

        finally:
            connector.close()
