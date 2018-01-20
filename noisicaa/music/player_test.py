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

import asyncio
import logging
from unittest import mock

from noisidev import unittest
from noisicaa import core
from noisicaa import audioproc
from noisicaa.core import ipc
from noisicaa.constants import TEST_OPTS

from . import project
from . import player

logger = logging.getLogger(__name__)


class MockAudioProcClient(object):
    def __init__(self, event_loop, server):
        self.audiostream_server = None
        self.listeners = core.CallbackRegistry()

    async def setup(self):
        pass

    async def cleanup(self):
        if self.audiostream_server is not None:
            self.audiostream_server.cleanup()
            self.audiostream_server = None

    async def connect(self, address):
        logger.info("Connecting to audioproc client at %s...", address)

    async def disconnect(self, shutdown=False):
        logger.info("Disconnect audioproc client (shutdown=%s).", shutdown)

    async def pipeline_mutation(self, mutation):
        pass

    async def set_backend(self, backend, **settings):
        logger.info("Set to audioproc backend to %s.", backend)
        if backend == 'ipc':
            self.audiostream_server = audioproc.AudioStream.create_server(settings['ipc_address'])
            self.audiostream_server.setup()
        else:
            raise ValueError("Unexpected backend '%s'" % backend)

    async def dump(self):
        pass

    async def update_project_properties(self, bpm=None, duration=None):
        assert bpm is None or isinstance(bpm, int)
        assert duration is None or isinstance(duration, audioproc.MusicalDuration)

    def kill_backend(self):
        self.audiostream_server.cleanup()
        self.audiostream_server = None


class PlayerTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.project = project.BaseProject()

        self.player_status_calls = asyncio.Queue()
        self.callback_server = ipc.Server(self.loop, 'callback', socket_dir=TEST_OPTS.TMP_DIR)
        self.callback_server.add_command_handler(
            'PLAYER_STATUS',
            lambda player_id, kwargs: self.player_status_calls.put_nowait(kwargs))
        await self.callback_server.setup()

        self.audioproc_server = ipc.Server(self.loop, 'audioproc', socket_dir=TEST_OPTS.TMP_DIR)
        await self.audioproc_server.setup()

        self.mock_manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            assert cmd == 'CREATE_AUDIOPROC_PROCESS'
            name, = args
            assert name == 'player'
            return self.audioproc_server.address
        self.mock_manager.call.side_effect = mock_call

        logger.info("Testcase setup complete.")

    async def cleanup_testcase(self):
        logger.info("Testcase teardown starts...")

        await self.audioproc_server.cleanup()
        await self.callback_server.cleanup()

    async def test_audio_stream_fails(self):
        p = player.Player(
            project=self.project,
            callback_address=self.callback_server.address,
            manager=self.mock_manager,
            event_loop=self.loop,
            tmp_dir=TEST_OPTS.TMP_DIR)
        try:
            with mock.patch('noisicaa.music.player.AudioProcClient', MockAudioProcClient):
                await p.setup()

                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'starting'})
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'running'})

                logger.info("Backend closes its pipe...")
                p.audioproc_backend.backend_crashed()

                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'crashed'})

                logger.info("Waiting until audioproc is down...")
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'stopped'})

                # TODO: verify that backend gets restarted correctly (currently it doesn't).

                # need some time to finish the IPC response of the last PLAYER_STATUS call
                # TODO: server shutdown should lame duck and wait until all pending
                # calls are finished.
                await asyncio.sleep(0.1)
        finally:
            await p.cleanup()
