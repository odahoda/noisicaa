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

# This file triggers https://github.com/JukkaL/mypy/issues/730
# mypy: skip-file

import asyncio
import contextlib
import logging
import os
import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisidev import perf_stats
from noisicaa.constants import TEST_OPTS
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.audioproc import audioproc_client
from noisicaa.bindings import lv2
from noisicaa.core import ipc

from . import project
from . import player

logger = logging.getLogger(__name__)


class TestAudioProcClientImpl(object):
    def __init__(self, event_loop, name):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, name, socket_dir=TEST_OPTS.TMP_DIR)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()

class TestAudioProcClient(
        audioproc_client.AudioProcClientMixin, TestAudioProcClientImpl):
    pass


class NodeDBClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class NodeDBClient(node_db.NodeDBClientMixin, NodeDBClientImpl):
    pass


UNSET = object()

class CallbackServer(ipc.Server):
    def __init__(self, event_loop):
        super().__init__(event_loop, 'callback', socket_dir=TEST_OPTS.TMP_DIR)

        self.player_status_calls = asyncio.Queue(loop=event_loop)
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


class PlayerTest(
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.callback_server = None
        self.node_db_client = None
        self.audioproc_address_player = None
        self.audioproc_address_main = None
        self.audioproc_client_main = None
        self.project = None

    async def setup_testcase(self):
        os.environ['LADSPA_PATH'] = '/usr/lib/ladspa'
        os.environ['LV2_PATH'] = '/usr/lib/lv2'

        self.setup_node_db_process(inline=True)
        self.setup_urid_mapper_process(inline=True)
        self.setup_audioproc_process(inline=True)
        self.setup_plugin_host_process(inline=True)

        self.callback_server = CallbackServer(self.loop)
        await self.callback_server.setup()

        node_db_address = await self.process_manager_client.call('CREATE_NODE_DB_PROCESS')
        self.node_db_client = NodeDBClient(self.loop, self.callback_server)
        await self.node_db_client.setup()
        await self.node_db_client.connect(node_db_address)

        self.audioproc_address_main = await self.process_manager_client.call(
            'CREATE_AUDIOPROC_PROCESS', 'main_process')

        self.audioproc_client_main = TestAudioProcClient(self.loop, 'main_client')
        await self.audioproc_client_main.setup()
        await self.audioproc_client_main.connect(
            self.audioproc_address_main, flags={'perf_data'})
        await self.audioproc_client_main.set_backend(TEST_OPTS.PLAYBACK_BACKEND)

        self.project = demo_project.complex(project.BaseProject, node_db=self.node_db_client)

        logger.info("Testcase setup complete.")

    async def cleanup_testcase(self):
        logger.info("Testcase teardown starts...")

        if self.node_db_client is not None:
            await self.node_db_client.disconnect()
            await self.node_db_client.cleanup()

        if self.callback_server is not None:
            await self.callback_server.cleanup()

    @contextlib.contextmanager
    def track_frame_stats(self, testname):
        frame_times = []

        def log_stats(spans, parent_id, indent):
            for span in spans:
                if span.parentId == parent_id:
                    logger.debug(
                        "%-40s: %10.3fµs",
                        '  ' * indent + span.name,
                        (span.endTimeNSec - span.startTimeNSec) / 1000.0)
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
        p = player.Player(
            project=self.project,
            callback_address=self.callback_server.address,
            event_loop=self.loop,
            audioproc_client=self.audioproc_client_main,
            realm='root')
        try:
            logger.info("Setup player...")
            await p.setup()
            logger.info("Player setup complete.")

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

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()

    @unittest.skip("TODO: async status updates are flaky")
    async def test_send_message(self):
        p = player.Player(
            project=self.project,
            callback_address=self.callback_server.address,
            event_loop=self.loop,
            audioproc_client=self.audioproc_client_main,
            realm='root')
        try:
            await p.setup()

            logger.info("Wait until audioproc is ready...")
            self.assertEqual(
                await self.callback_server.wait_for('pipeline_state'),
                'starting')
            self.assertEqual(
                await self.callback_server.wait_for('pipeline_state'),
                'running')
            logger.info("audioproc is ready...")

            await asyncio.sleep(0.2, loop=self.loop)

            logger.info("Send messsage...")
            p.send_message(core.build_message(
                {core.MessageKey.trackId: self.project.master_group.tracks[0].id},
                core.MessageType.atom,
                lv2.AtomForge.build_midi_noteon(0, 65, 127)).to_bytes())

            # TODO: wait for player ready (node setup complete).
            await asyncio.sleep(1, loop=self.loop)

        except:
            logger.exception("")
            raise

        finally:
            await p.cleanup()
