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

import async_generator

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa import node_db
from noisicaa.constants import TEST_OPTS
from noisicaa.core import ipc

from . import audioproc_client

logger = logging.getLogger(__name__)


class TestClientImpl(audioproc_client.AudioProcClientBase):  # pylint: disable=abstract-method
    def __init__(self, event_loop):
        super().__init__(event_loop, ipc.Server(event_loop, 'client', TEST_OPTS.TMP_DIR))

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(audioproc_client.AudioProcClientMixin, TestClientImpl):
    pass


class AudioProcClientTest(
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.passthru_description = node_db.NodeDescription(
            type=node_db.NodeDescription.PROCESSOR,
            ports=[
                node_db.PortDescription(
                    name='in:left',
                    direction=node_db.PortDescription.INPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
                node_db.PortDescription(
                    name='in:right',
                    direction=node_db.PortDescription.INPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
                node_db.PortDescription(
                    name='out:left',
                    direction=node_db.PortDescription.OUTPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
                node_db.PortDescription(
                    name='out:right',
                    direction=node_db.PortDescription.OUTPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
            ],
            processor=node_db.ProcessorDescription(
                type=node_db.ProcessorDescription.NULLPROC,
            ),
        )

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_process(self, *, inline_plugin_host=True, inline_audioproc=True):
        self.setup_urid_mapper_process(inline=True)
        self.setup_plugin_host_process(inline=inline_plugin_host)

        if inline_audioproc:
            proc = await self.process_manager.start_inline_process(
                name='audioproc',
                entry='noisicaa.audioproc.audioproc_process.AudioProcProcess')
        else:
            proc = await self.process_manager.start_subprocess(
                name='audioproc',
                entry='noisicaa.audioproc.audioproc_process.AudioProcSubprocess')

        client = TestClient(self.loop)
        await client.setup()
        await client.connect(proc.address)
        try:
            await client.create_realm(name='root')

            await async_generator.yield_(client)
        finally:
            await client.disconnect(shutdown=True)
            await client.cleanup()

            await proc.wait()

    async def test_realms(self):
        async with self.create_process(inline_plugin_host=False) as client:
            await client.create_realm(name='test', parent='root')

            await client.add_node(
                'root',
                id='child', child_realm='test', description=node_db.Builtins.ChildRealmDescription)
            await client.connect_ports('root', 'child', 'out:left', 'sink', 'in:left')
            await client.connect_ports('root', 'child', 'out:right', 'sink', 'in:right')

            await client.disconnect_ports('root', 'child', 'out:left', 'sink', 'in:left')
            await client.disconnect_ports('root', 'child', 'out:right', 'sink', 'in:right')
            await client.remove_node('root', 'child')

            await client.delete_realm('test')

    async def test_add_remove_node(self):
        async with self.create_process() as client:
            await client.add_node('root', id='test', description=self.passthru_description)
            await client.remove_node('root', 'test')

    async def test_connect_ports(self):
        async with self.create_process() as client:
            await client.add_node('root', id='node1', description=self.passthru_description)
            await client.add_node('root', id='node2', description=self.passthru_description)
            await client.connect_ports('root', 'node1', 'out:left', 'node2', 'in:left')

    async def test_disconnect_ports(self):
        async with self.create_process() as client:
            await client.add_node('root', id='node1', description=self.passthru_description)
            await client.add_node('root', id='node2', description=self.passthru_description)
            await client.connect_ports('root', 'node1', 'out:left', 'node2', 'in:left')
            await client.disconnect_ports('root', 'node1', 'out:left', 'node2', 'in:left')

    async def test_plugin_node(self):
        async with self.create_process() as client:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
            node_description = self.node_db[plugin_uri]
            await client.add_node('root', id='test', description=node_description)
            await client.remove_node('root', 'test')

    async def test_plugin_host_process_crashes(self):
        async with self.create_process(inline_plugin_host=False) as client:
            is_broken = asyncio.Event(loop=self.loop)

            def pipeline_status(status):
                logger.info("pipeline_status(%s)", status)
                if 'node_state' in status:
                    realm, node_id, node_state = status['node_state']
                    if realm == 'root' and node_id == 'test' and node_state == 'BROKEN':
                        is_broken.set()
            client.listeners.add('pipeline_status', pipeline_status)

            await client.set_backend('null')

            plugin_uri = 'ladspa://crasher.so/crasher'
            node_description = self.node_db[plugin_uri]
            await client.add_node('root', id='test', description=node_description)

            await asyncio.wait_for(is_broken.wait(), 10, loop=self.loop)

            # TODO: this should not crash, when plugin host process is dead.
            #await client.remove_node('test')
