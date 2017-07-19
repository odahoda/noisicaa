#!/usr/bin/python3

import asyncio
import logging
import os.path
import tempfile
import threading
import time
import uuid
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa import audioproc
from noisicaa.audioproc import audioproc_process
from noisicaa.audioproc import audioproc_client
from noisicaa.bindings import lv2
from noisicaa.core import ipc
from noisicaa.ui import model
from noisicaa.node_db.private import db as node_db

from . import project
from . import sheet
from . import player
from . import project_client

logger = logging.getLogger(__name__)


class TestAudioProcProcessImpl(object):
    def __init__(self, event_loop, name):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, name)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestAudioProcProcess(
        audioproc_process.AudioProcProcessMixin, TestAudioProcProcessImpl):
    pass


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


class CallbackServer(ipc.Server):
    def __init__(self, event_loop):
        super().__init__(event_loop, 'callback')

        self.player_status_calls = asyncio.Queue()
        self.add_command_handler(
            'PLAYER_STATUS', self.handle_player_update,
            log_level=logging.DEBUG)

    async def handle_player_update(self, player_id, kwargs):
        self.player_status_calls.put_nowait(kwargs)

    async def wait_for(self, name):
        while True:
            status = await self.player_status_calls.get()
            if name in status:
                return status[name]


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
        self.sheet = self.project.sheets[0]

        self.callback_server = CallbackServer(self.loop)
        await self.callback_server.setup()

        self.audioproc_server_main = TestAudioProcProcess(self.loop, 'main_process')
        await self.audioproc_server_main.setup()
        self.audioproc_server_main_task = self.loop.create_task(
            self.audioproc_server_main.run())

        self.audioproc_client_main = TestAudioProcClient(self.loop, 'main_client')
        await self.audioproc_client_main.setup()
        await self.audioproc_client_main.connect(
            self.audioproc_server_main.server.address)
        await self.audioproc_client_main.set_backend('pyaudio', frame_size=1024)

        self.audioproc_server_player = TestAudioProcProcess(self.loop, 'player_process')
        await self.audioproc_server_player.setup()
        self.audioproc_server_player_task = self.loop.create_task(
            self.audioproc_server_player.run())

        self.mock_manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            assert cmd == 'CREATE_AUDIOPROC_PROCESS'
            name, = args
            assert name == 'player'
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

    async def test_playback_demo(self):
        p = player.Player(self.sheet, self.callback_server.address, self.mock_manager, self.loop)
        try:
            await p.setup()

            player_node_id = await self.audioproc_client_main.add_node(
                'ipc', address=p.proxy_address)
            await self.audioproc_client_main.connect_ports(
                player_node_id, 'out:left', 'sink', 'in:left')
            await self.audioproc_client_main.connect_ports(
                player_node_id, 'out:right', 'sink', 'in:right')
            try:
                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'starting')
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'running')

                await p.update_settings(project_client.PlayerSettings(state='playing'))

                self.assertEqual(
                    await self.callback_server.wait_for('player_state'),
                    'playing')

                logger.info("Waiting for end")

                self.assertEqual(
                    await self.callback_server.wait_for('player_state'),
                    'stopped')

            finally:
                await self.audioproc_client_main.disconnect_ports(
                    player_node_id, 'out:left', 'sink', 'in:left')
                await self.audioproc_client_main.disconnect_ports(
                    player_node_id, 'out:right', 'sink', 'in:right')
                await self.audioproc_client_main.remove_node(player_node_id)

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()

    async def test_send_message(self):
        p = player.Player(self.sheet, self.callback_server.address, self.mock_manager, self.loop)
        try:
            await p.setup()

            player_node_id = await self.audioproc_client_main.add_node(
                'ipc', address=p.proxy_address)
            await self.audioproc_client_main.connect_ports(
                player_node_id, 'out:left', 'sink', 'in:left')
            await self.audioproc_client_main.connect_ports(
                player_node_id, 'out:right', 'sink', 'in:right')
            try:
                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'starting')
                self.assertEqual(
                    await self.callback_server.wait_for('pipeline_state'),
                    'running')
                logger.info("audioproc is ready...")

                logger.info("Send messsage...")
                p.send_message(core.build_message(
                    {core.MessageKey.trackId: self.sheet.master_group.tracks[0].id},
                    core.MessageType.atom,
                    lv2.AtomForge.build_midi_noteon(0, 65, 127)))

                # TODO: wait for player ready (node setup complete).
                await asyncio.sleep(1)

            finally:
                await self.audioproc_client_main.disconnect_ports(
                    player_node_id, 'out:left', 'sink', 'in:left')
                await self.audioproc_client_main.disconnect_ports(
                    player_node_id, 'out:right', 'sink', 'in:right')
                await self.audioproc_client_main.remove_node(player_node_id)

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()


if __name__ == '__main__':
    unittest.main()
