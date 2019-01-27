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


import asyncio
import logging

from noisidev import unittest
from noisicaa import audioproc
from noisicaa.core import ipc
from noisicaa.constants import TEST_OPTS
from noisicaa.builtin_nodes.score_track import server_impl as score_track
from . import project
from . import player

logger = logging.getLogger(__name__)


class MockAudioProcClient(audioproc.AudioProcClientBase):  # pylint: disable=abstract-method
    def __init__(self):
        super().__init__(None, None)

    async def setup(self):
        pass

    async def cleanup(self):
        pass

    async def connect(self, address):
        logger.info("Connecting to audioproc client at %s...", address)

    async def disconnect(self, shutdown=False):
        logger.info("Disconnect audioproc client (shutdown=%s).", shutdown)

    async def pipeline_mutation(self, realm, mutation):
        assert realm == 'player'

    async def send_node_messages(self, realm, messages):
        assert realm == 'player'

    async def update_project_properties(self, realm, bpm=None, duration=None):
        assert realm == 'player'
        assert bpm is None or isinstance(bpm, int)
        assert duration is None or isinstance(duration, audioproc.MusicalDuration)


class PlayerTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()
        self.project = self.pool.create(project.BaseProject)

        self.player_status_calls = asyncio.Queue(loop=self.loop)  # type: asyncio.Queue
        self.callback_server = ipc.Server(self.loop, 'callback', socket_dir=TEST_OPTS.TMP_DIR)
        self.callback_server.add_command_handler(
            'PLAYER_STATUS',
            lambda player_id, kwargs: self.player_status_calls.put_nowait(kwargs))
        await self.callback_server.setup()

        self.audioproc_server = ipc.Server(self.loop, 'audioproc', socket_dir=TEST_OPTS.TMP_DIR)
        await self.audioproc_server.setup()

        logger.info("Testcase setup complete.")

    async def cleanup_testcase(self):
        logger.info("Testcase teardown starts...")

        await self.audioproc_server.cleanup()
        await self.callback_server.cleanup()

    async def test_playback(self):
        p = player.Player(
            project=self.project,
            callback_address=self.callback_server.address,
            event_loop=self.loop,
            audioproc_client=MockAudioProcClient(),
            realm='player')
        try:
            await p.setup()

            track1 = self.pool.create(score_track.ScoreTrack, name="Track 1")
            self.project.add_node(track1)


        finally:
            await p.cleanup()
