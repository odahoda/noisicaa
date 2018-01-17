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

from unittest import mock

import asynctest

from noisicaa import audioproc
from noisicaa.node_db.private import db as node_db

from . import project
from . import control_track


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]


class ControlTrackConnectorTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = project.BaseProject.make_demo(node_db=self.node_db)
        self.track = control_track.ControlTrack(name='test')
        self.project.master_group.tracks.append(self.track)

        self.messages = []

        self.player = mock.Mock()
        def send_node_message(node_id, msg):
            self.assertEqual(node_id, self.track.generator_name)
            # TODO: track the messages themselves and inspect their contents as well.
            self.messages.append(msg.WhichOneof('msg'))
        self.player.send_node_message.side_effect = send_node_message

    async def tearDown(self):
        await self.node_db.cleanup()

    def test_messages_on_mutations(self):
        connector = self.track.create_player_connector(self.player)
        try:
            self.messages.clear()
            self.track.points.insert(
                0,
                control_track.ControlPoint(time=audioproc.MusicalTime(1, 4), value=0.5))
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point'])

            self.messages.clear()
            self.track.points.insert(
                1,
                control_track.ControlPoint(time=audioproc.MusicalTime(2, 4), value=0.8))
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point'])

            self.messages.clear()
            del self.track.points[0]
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point'])

            self.messages.clear()
            self.track.points[0].value = 0.2
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point',
                 'cvgenerator_add_control_point'])

            self.messages.clear()
            self.track.points[0].time = audioproc.MusicalTime(3, 4)
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point',
                 'cvgenerator_add_control_point'])

        finally:
            connector.close()

    def test_messages_on_init(self):
        self.track.points.insert(
            0,
            control_track.ControlPoint(time=audioproc.MusicalTime(1, 4), value=0.5))
        self.track.points.insert(
            1,
            control_track.ControlPoint(time=audioproc.MusicalTime(2, 4), value=0.8))

        connector = self.track.create_player_connector(self.player)
        try:
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point',
                 'cvgenerator_add_control_point'])

        finally:
            connector.close()
