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

from noisidev import unittest
from noisidev import demo_project
from noisicaa.node_db.private import db as node_db
from . import pitch
from . import project
from . import score_track


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db[uri]



class ScoreTrackConnectorTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

    async def cleanup_testcase(self):
        await self.node_db.cleanup()

    def test_foo(self):
        pr = demo_project.basic(project.BaseProject, node_db=self.node_db)
        tr = pr.master_group.tracks[0]

        messages = []

        connector = tr.create_track_connector(message_cb=messages.append)
        try:
            messages.extend(connector.init())

            pr.property_track.insert_measure(1)
            tr.insert_measure(1)
            m = tr.measure_list[1].measure
            m.notes.append(score_track.Note(pitches=[pitch.Pitch('D#4')]))

            self.assertTrue(len(messages) > 0)

        finally:
            connector.close()
