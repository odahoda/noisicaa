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

import async_generator

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import lv2
from noisicaa import node_db
from noisicaa import editor_main_pb2
from . import audioproc_client
from .public import engine_notification_pb2

logger = logging.getLogger(__name__)


class AudioProcClientTest(
        unittest_mixins.ServerMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.passthru_description = node_db.NodeDescription(
            uri='test://passthru',
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
                type='builtin://null',
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

        create_urid_mapper_response = editor_main_pb2.CreateProcessResponse()
        await self.process_manager_client.call(
            'CREATE_URID_MAPPER_PROCESS', None, create_urid_mapper_response)
        urid_mapper_address = create_urid_mapper_response.address

        urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=TEST_OPTS.TMP_DIR)
        await urid_mapper.setup(self.loop)

        client = audioproc_client.AudioProcClient(self.loop, self.server, urid_mapper)
        await client.setup()
        await client.connect(proc.address)
        try:
            await client.create_realm(name='root')

            await async_generator.yield_(client)
        finally:
            await client.disconnect()
            await client.cleanup()

            await urid_mapper.cleanup(self.loop)

            await proc.shutdown()

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

            def engine_notification(msg):
                logger.info("engine_notification:\n%s", msg)
                for node_state_change in msg.node_state_changes:
                    if (node_state_change.realm == 'root'
                            and node_state_change.node_id == 'test'
                            and (node_state_change.state
                                 == engine_notification_pb2.NodeStateChange.BROKEN)):
                        is_broken.set()
            client.engine_notifications.add(engine_notification)

            await client.set_backend('null')

            plugin_uri = 'ladspa://crasher.so/crasher'
            node_description = self.node_db[plugin_uri]
            await client.add_node('root', id='test', description=node_description)

            await asyncio.wait_for(is_broken.wait(), 10, loop=self.loop)

            # TODO: this should not crash, when plugin host process is dead.
            #await client.remove_node('test')
