#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import contextlib
import logging
import os.path
import tempfile
import unittest
from unittest import mock

import asynctest

from noisicaa import constants
from noisicaa import core
from noisicaa import audioproc
from noisicaa.audioproc import audioproc_process
from noisicaa.audioproc import audioproc_client
from noisicaa.bindings import lv2
from noisicaa.core import ipc
from noisicaa.node_db.private import db as node_db
from noisidev import perf_stats

from . import project
from . import player

logger = logging.getLogger(__name__)


class TestAudioProcClientImpl(object):
    def __init__(self, event_loop, name):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, name)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestAudioProcClient(
        audioproc_client.AudioProcClientMixin, TestAudioProcClientImpl):
    pass


UNSET = object()

class CallbackServer(ipc.Server):
    def __init__(self, event_loop):
        super().__init__(event_loop, 'callback')

        self.player_status_calls = asyncio.Queue()
        self.add_command_handler(
            'PLAYER_STATUS', self.handle_player_update,
            log_level=logging.DEBUG)

    async def handle_player_update(self, player_id, kwargs):
        self.player_status_calls.put_nowait(kwargs)

    async def wait_for(self, name, value=UNSET):
        while True:
            status = await self.player_status_calls.get()
            if name in status:
                if value is UNSET or status[name] == value:
                    return status[name]

    async def wait_for_player_state(self, name, value=UNSET):
        while True:
            status = await self.player_status_calls.get()
            if 'player_state' in status:
                state = status['player_state']
                if state.HasField(name):
                    if value is UNSET or getattr(state, name) == value:
                        return getattr(state, name)


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]


class PlayerTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

        self.project = project.BaseProject.make_demo(demo='complex', node_db=self.node_db)

        self.callback_server = CallbackServer(self.loop)
        await self.callback_server.setup()

        self.audioproc_server_main = audioproc_process.AudioProcProcess(
            name='main_process', event_loop=self.loop, manager=None)
        await self.audioproc_server_main.setup()
        self.audioproc_server_main_task = self.loop.create_task(
            self.audioproc_server_main.run())

        self.audioproc_client_main = TestAudioProcClient(self.loop, 'main_client')
        await self.audioproc_client_main.setup()
        await self.audioproc_client_main.connect(
            self.audioproc_server_main.server.address, flags={'perf_data'})
        await self.audioproc_client_main.set_backend(constants.TEST_OPTS.PLAYBACK_BACKEND)

        profile_path = None
        if constants.TEST_OPTS.ENABLE_PROFILER:
            profile_path = os.path.join(tempfile.gettempdir(), self.id() + '.prof')
        self.audioproc_server_player = audioproc_process.AudioProcProcess(
            name='player_process', event_loop=self.loop, manager=None,
            profile_path=profile_path, enable_player=True)
        await self.audioproc_server_player.setup()
        self.audioproc_server_player_task = self.loop.create_task(
            self.audioproc_server_player.run())

        self.mock_manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            assert cmd == 'CREATE_AUDIOPROC_PROCESS'
            name, = args
            assert name == 'player'
            assert kwargs.get('enable_player', False)
            return self.audioproc_server_player.server.address
        self.mock_manager.call.side_effect = mock_call

        logger.info("Testcase setup complete.")

    async def tearDown(self):
        logger.info("Testcase teardown starts...")

        await asyncio.wait_for(self.audioproc_server_player_task, None)
        await self.audioproc_server_player.cleanup()
        await self.audioproc_client_main.disconnect(shutdown=True)
        await self.audioproc_client_main.cleanup()

        await asyncio.wait_for(self.audioproc_server_main_task, None)
        await self.audioproc_server_main.cleanup()

        await self.callback_server.cleanup()

        await self.node_db.cleanup()

    @contextlib.contextmanager
    def track_frame_stats(self, testname):
        frame_times = []

        def log_stats(spans, parent_id, indent):
            for span in spans:
                if span.parentId == parent_id:
                    logger.info("%-40s: %10.3fµs", '  ' * indent + span.name, (span.endTimeNSec - span.startTimeNSec) / 1000.0)
                    log_stats(spans, span.id, indent+1)

        def cb(status):
            perf_data = status.get('perf_data', None)
            if perf_data:
                topspan = perf_data.spans[0]
                assert topspan.parentId == 0
                assert topspan.name == 'frame'
                duration = (topspan.endTimeNSec - topspan.startTimeNSec) / 1000.0
                frame_times.append(duration)
                log_stats(sorted(perf_data.spans, key=lambda s: s.startTimeNSec), 0, 0)

        listener = self.audioproc_client_main.listeners.add('pipeline_status', cb)
        try:
            yield

            perf_stats.write_frame_stats(
                os.path.splitext(os.path.basename(__file__))[0],
                testname, frame_times)

        finally:
            listener.remove()

    @unittest.skip("TODO: async status updates are flaky")
    async def test_playback_demo(self):
        p = player.Player(self.project, self.callback_server.address, self.mock_manager, self.loop)
        try:
            logger.info("Setup player...")
            await p.setup()
            logger.info("Player setup complete.")

            await self.audioproc_client_main.add_node(
                description=self.node_db.get_node_description('builtin://ipc'),
                id='player',
                initial_parameters=dict(ipc_address=p.audiostream_address))
            await self.audioproc_client_main.connect_ports(
                'player', 'out:left', 'sink', 'in:left')
            await self.audioproc_client_main.connect_ports(
                'player', 'out:right', 'sink', 'in:right')
            try:
                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'starting')
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'running')

                with self.track_frame_stats('playback_demo'):
                    logger.info("Start playback...")
                    await p.update_state(audioproc.PlayerState(playing=True))

                    await self.callback_server.wait_for_player_state('playing', True)

                    logger.info("Waiting for end...")

                    await self.callback_server.wait_for_player_state('playing', False)
                    logger.info("Playback finished.")

            finally:
                await self.audioproc_client_main.disconnect_ports(
                    'player', 'out:left', 'sink', 'in:left')
                await self.audioproc_client_main.disconnect_ports(
                    'player', 'out:right', 'sink', 'in:right')
                await self.audioproc_client_main.remove_node('player')

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()

    @unittest.skip("TODO: async status updates are flaky")
    async def test_send_message(self):
        p = player.Player(self.project, self.callback_server.address, self.mock_manager, self.loop)
        try:
            await p.setup()

            await self.audioproc_client_main.add_node(
                description=self.node_db.get_node_description('builtin://ipc'),
                id='player',
                initial_parameters=dict(ipc_address=p.audiostream_address))
            await self.audioproc_client_main.connect_ports(
                'player', 'out:left', 'sink', 'in:left')
            await self.audioproc_client_main.connect_ports(
                'player', 'out:right', 'sink', 'in:right')
            try:
                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'starting')
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'running')
                logger.info("audioproc is ready...")

                await asyncio.sleep(0.2)

                logger.info("Send messsage...")
                p.send_message(core.build_message(
                    {core.MessageKey.trackId: self.project.master_group.tracks[0].id},
                    core.MessageType.atom,
                    lv2.AtomForge.build_midi_noteon(0, 65, 127)).to_bytes())

                # TODO: wait for player ready (node setup complete).
                await asyncio.sleep(1)

            finally:
                await self.audioproc_client_main.disconnect_ports(
                    'player', 'out:left', 'sink', 'in:left')
                await self.audioproc_client_main.disconnect_ports(
                    'player', 'out:right', 'sink', 'in:right')
                await self.audioproc_client_main.remove_node('player')

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()


if __name__ == '__main__':
    unittest.main()
