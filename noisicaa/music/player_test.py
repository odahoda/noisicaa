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
from noisicaa.core import ipc
from noisicaa.ui import model

from . import project
from . import sheet
from . import player

logger = logging.getLogger(__name__)


class MockAudioProcClient(object):
    def __init__(self, event_loop, server):
        self.audiostream_server = None
        self.backend_thread = None
        self.stop_backend = None
        self.listeners = core.CallbackRegistry()

    async def setup(self):
        pass

    async def cleanup(self):
        if self.backend_thread is not None:
            self.backend_thread.join()
            self.backend_thread = None

        if self.audiostream_server is not None:
            self.audiostream_server.cleanup()
            self.audiostream_server = None

    async def connect(self, address):
        logger.info("Connecting to audioproc client at %s...", address)

    async def disconnect(self, shutdown=False):
        logger.info("Disconnect audioproc client (shutdown=%s).", shutdown)

    async def set_backend(self, backend):
        logger.info("Set to audioproc backend to %s.", backend)
        if backend == 'ipc':
            address = os.path.join(
                tempfile.gettempdir(), 'audioproc.%s.pipe' % uuid.uuid4().hex)
            self.audiostream_server = audioproc.AudioStreamServer(address)
            self.audiostream_server.setup()
            self.stop_backend = threading.Event()
            self.backend_thread = threading.Thread(target=self.backend_main)
            self.backend_thread.start()
            return address
        return None

    async def dump(self):
        pass

    def kill_backend(self):
        self.stop_backend.set()
        self.backend_thread.join()
        self.backend_thread = None
        self.audiostream_server.cleanup()
        self.audiostream_server = None

    def backend_main(self):
        try:
            while not self.stop_backend.is_set():
                logger.debug("Waiting for request...")
                request = self.audiostream_server.receive_frame()
                logger.debug("Got request %s, sending response.", request.samplePos)

                response = audioproc.FrameData.new_message(**request.to_dict())
                self.audiostream_server.send_frame(response)
        except audioproc.StreamClosed:
            pass

class PlayerTest(asynctest.TestCase):
    async def setUp(self):
        self.project = project.BaseProject()
        self.sheet = sheet.Sheet(name='Test')
        self.project.sheets.append(self.sheet)

        self.player_status_calls = asyncio.Queue()
        self.callback_server = ipc.Server(self.loop, 'callback')
        self.callback_server.add_command_handler(
            'PLAYER_STATUS',
            lambda player_id, kwargs: self.player_status_calls.put_nowait(kwargs))
        await self.callback_server.setup()

        self.audioproc_server = ipc.Server(self.loop, 'audioproc')
        await self.audioproc_server.setup()

        self.mock_manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            assert cmd == 'CREATE_AUDIOPROC_PROCESS'
            name, = args
            assert name == 'player'
            return self.audioproc_server.address
        self.mock_manager.call.side_effect = mock_call

        self.proxy_client_thread = None

        logger.info("Testcase setup complete.")

    async def tearDown(self):
        logger.info("Testcase teardown starts...")

        if self.proxy_client_thread is not None:
            self.proxy_client_thread.join()
        await self.audioproc_server.cleanup()
        await self.callback_server.cleanup()

    def start_proxy_client(self, p):
        self.proxy_client_thread = threading.Thread(
            target=self.proxy_client_main, args=(p.proxy_address,))
        self.proxy_client_thread.start()

    def proxy_client_main(self, address):
        client = audioproc.AudioStreamClient(address)
        try:
            client.setup()

            sample_pos = 0
            while True:
                request = audioproc.FrameData.new_message()
                request.samplePos = sample_pos
                request.frameSize = 10
                logger.debug("Sending frame %s...", sample_pos)
                client.send_frame(request)
                logger.debug("Waiting for response...")
                response = client.receive_frame()
                logger.debug("Got response %s.", response.samplePos)

                sample_pos += 1

        except audioproc.StreamClosed:
            pass

        finally:
            client.cleanup()

    async def test_audio_stream_fails(self):
        p = player.Player(self.sheet, self.callback_server.address, self.mock_manager, self.loop)
        try:
            with mock.patch('noisicaa.music.player.AudioProcClient', MockAudioProcClient):
                await p.setup()
                self.start_proxy_client(p)

                logger.info("Wait until audioproc is ready...")
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'starting'})
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'running'})

                logger.info("Backend closes its pipe...")
                p.audioproc_client.kill_backend()
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'crashed'})

                logger.info("Waiting until audioproc is down...")
                self.assertEqual(
                    await self.player_status_calls.get(),
                    {'pipeline_state': 'stopped'})

                # need some time to finish the IPC response of the last PLAYER_STATUS call
                # TODO: server shutdown should lame duck and wait until all pending
                # calls are finished.
                await asyncio.sleep(0.1)
        finally:
            await p.cleanup()


if __name__ == '__main__':
    unittest.main()
