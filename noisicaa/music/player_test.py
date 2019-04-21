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


import logging

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import audioproc
from noisicaa.core import ipc
from noisicaa.core import session_data_pb2
from noisicaa.builtin_nodes.score_track import server_impl as score_track
from . import project
from . import player
from . import session_value_store

logger = logging.getLogger(__name__)


class MockAudioProcClient(audioproc.AbstractAudioProcClient):  # pylint: disable=abstract-method
    async def connect(self, address):
        logger.info("Connecting to audioproc client at %s...", address)

    async def disconnect(self):
        logger.info("Disconnect audioproc client.")

    async def pipeline_mutation(self, realm, mutation):
        assert realm == 'player'

    async def send_node_messages(self, realm, messages):
        assert realm == 'player'

    async def update_project_properties(self, realm, properties):
        assert realm == 'player'
        assert isinstance(properties, audioproc.ProjectProperties)

    async def set_session_values(self, realm, session_values):
        assert realm == 'player'
        assert all(isinstance(value, session_data_pb2.SessionValue) for value in session_values)


class PlayerTest(unittest_mixins.ServerMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()
        self.project = self.pool.create(project.BaseProject)

        cb_endpoint = ipc.ServerEndpoint('player_cb')
        self.cb_endpoint_address = await self.server.add_endpoint(cb_endpoint)

        self.session_values = session_value_store.SessionValueStore(self.loop, 'test')
        await self.session_values.init(TEST_OPTS.TMP_DIR)

    async def cleanup_testcase(self):
        await self.server.remove_endpoint('player_cb')

    async def test_playback(self):
        p = player.Player(
            project=self.project,
            callback_address=self.cb_endpoint_address,
            event_loop=self.loop,
            audioproc_client=MockAudioProcClient(),
            session_values=self.session_values,
            realm='player')
        try:
            await p.setup()

            track1 = self.pool.create(score_track.ScoreTrack, name="Track 1")
            self.project.add_node(track1)


        finally:
            await p.cleanup()
