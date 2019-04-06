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

from typing import cast

import logging
import os
import os.path
import threading
import time
import uuid

import async_generator

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa.constants import TEST_OPTS
from noisicaa.core import ipc
from noisicaa.audioproc.public import node_parameters_pb2
from . import plugin_host_pb2
from . import block_context
from . import buffers
from . import processor
from . import processor_plugin_pb2
from . import buffer_arena

logger = logging.getLogger(__name__)


class ProcessorPluginTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.setup_urid_mapper_process(inline=True)

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_process(self, *, inline_plugin_host=True):
        if inline_plugin_host:
            proc = await self.process_manager.start_inline_process(
                name='plugin_host',
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostProcess')
        else:
            proc = await self.process_manager.start_subprocess(
                name='plugin_host',
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess')

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect()
        try:
            await async_generator.yield_(stub)
        finally:
            await stub.close()
            await proc.shutdown()

    async def test_plugin(self):
        async with self.create_process() as plugin_host:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
            node_desc = self.node_db[plugin_uri]

            plugin_spec = plugin_host_pb2.PluginInstanceSpec()
            plugin_spec.realm = 'root'
            plugin_spec.node_id = '1234'
            plugin_spec.node_description.CopyFrom(node_desc)

            create_plugin_request = plugin_host_pb2.CreatePluginRequest(spec=plugin_spec)
            create_plugin_response = plugin_host_pb2.CreatePluginResponse()
            await plugin_host.call(
                'CREATE_PLUGIN', create_plugin_request, create_plugin_response)
            pipe_address = create_plugin_response.pipe_path

            proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
            proc.setup()
            params = node_parameters_pb2.NodeParameters()
            plugin_params = params.Extensions[processor_plugin_pb2.processor_plugin_parameters]
            plugin_params.plugin_pipe_path = pipe_address
            proc.set_parameters(params)

            arena = buffer_arena.PyBufferArena(2**20)
            buffer_mgr = unittest_engine_utils.BufferManager(self.host_system, arena)

            buffer_mgr.allocate_from_node_description(node_desc)
            buffer_mgr.allocate('plugin_cond', buffers.PyPluginCondBuffer())

            ctxt = block_context.PyBlockContext(buffer_arena=arena)
            ctxt.sample_pos = 1024

            buffer_mgr.connect_ports(proc, ctxt, node_desc)
            proc.connect_port(ctxt, 4, buffer_mgr.data('plugin_cond'))

            audio_in = buffer_mgr['audio_in']
            audio_out = buffer_mgr['audio_out']
            for i in range(self.host_system.block_size):
                audio_in[i] = 0.5
                audio_out[i] = 0.0

            proc.process_block(ctxt, None)  # TODO: pass time_mapper

            for i in range(self.host_system.block_size):
                self.assertAlmostEqual(audio_out[i], 0.5)

            proc.cleanup()

            await plugin_host.call(
                'DELETE_PLUGIN',
                plugin_host_pb2.DeletePluginRequest(
                    realm=plugin_spec.realm, node_id=plugin_spec.node_id))

    async def test_pipe_closed(self):
        plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
        node_desc = self.node_db[plugin_uri]

        arena = buffer_arena.PyBufferArena(2**20)
        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system, arena)
        buffer_mgr.allocate_from_node_description(node_desc)
        buffer_mgr.allocate('plugin_cond', buffers.PyPluginCondBuffer())

        pipe_address = os.path.join(TEST_OPTS.TMP_DIR, 'pipe.%s' % uuid.uuid4().hex)
        os.mkfifo(pipe_address)

        fake_host_ready = threading.Event()
        fake_host_stop = threading.Event()
        def fake_host():
            fd = os.open(pipe_address, os.O_RDONLY | os.O_NONBLOCK)
            fake_host_ready.set()

            logger.info("Fake host waiting...")
            while not fake_host_stop.is_set() and not os.read(fd, 1):
                time.sleep(0.02)
            logger.info("Closing pipe...")
            os.close(fd)

            logger.info("Set plugin condition...")
            cond_type = cast(buffers.PyPluginCondBuffer, buffer_mgr.type('plugin_cond'))
            cond_buf = buffer_mgr['plugin_cond']
            cond_type.set_cond(cond_buf)

            logger.info("Fake host finished.")

        fake_host_thread = threading.Thread(target=fake_host)
        fake_host_thread.start()
        try:
            fake_host_ready.wait()

            proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
            proc.setup()
            params = node_parameters_pb2.NodeParameters()
            plugin_params = params.Extensions[processor_plugin_pb2.processor_plugin_parameters]
            plugin_params.plugin_pipe_path = pipe_address
            proc.set_parameters(params)

            ctxt = block_context.PyBlockContext(buffer_arena=arena)
            ctxt.sample_pos = 1024

            buffer_mgr.connect_ports(proc, ctxt, node_desc)
            proc.connect_port(ctxt, 4, buffer_mgr.data('plugin_cond'))

            audio_in = buffer_mgr['audio_in']
            audio_out = buffer_mgr['audio_out']
            for _ in range(10):
                for i in range(self.host_system.block_size):
                    audio_in[i] = 0.5
                    audio_out[i] = 0.0

                proc.process_block(ctxt, None)  # TODO: pass time_mapper
                if proc.state == processor.State.BROKEN:
                    break

            self.assertEqual(proc.state, processor.State.BROKEN)

            proc.cleanup()

        finally:
            fake_host_stop.set()
            fake_host_thread.join()

    async def test_plugin_blocked(self):
        plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
        node_desc = self.node_db[plugin_uri]

        arena = buffer_arena.PyBufferArena(2**20)
        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system, arena)
        buffer_mgr.allocate_from_node_description(node_desc)
        buffer_mgr.allocate('plugin_cond', buffers.PyPluginCondBuffer())

        pipe_address = os.path.join(TEST_OPTS.TMP_DIR, 'pipe.%s' % uuid.uuid4().hex)
        os.mkfifo(pipe_address)

        fake_host_ready = threading.Event()
        fake_host_quit = threading.Event()
        def fake_host():
            fd = os.open(pipe_address, os.O_RDONLY | os.O_NONBLOCK)
            fake_host_ready.set()

            logger.info("Fake host waiting...")
            while not fake_host_quit.is_set():
                while os.read(fd, 1):
                    break
                time.sleep(0.02)

            logger.info("Closing pipe...")
            os.close(fd)
            logger.info("Fake host finished.")

        fake_host_thread = threading.Thread(target=fake_host)
        fake_host_thread.start()
        try:
            fake_host_ready.wait()

            proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
            proc.setup()
            params = node_parameters_pb2.NodeParameters()
            plugin_params = params.Extensions[processor_plugin_pb2.processor_plugin_parameters]
            plugin_params.plugin_pipe_path = pipe_address
            proc.set_parameters(params)

            ctxt = block_context.PyBlockContext(buffer_arena=arena)
            ctxt.sample_pos = 1024

            buffer_mgr.connect_ports(proc, ctxt, node_desc)
            proc.connect_port(ctxt, 4, buffer_mgr.data('plugin_cond'))

            audio_in = buffer_mgr['audio_in']
            audio_out = buffer_mgr['audio_out']
            for _ in range(10):
                for i in range(self.host_system.block_size):
                    audio_in[i] = 0.5
                    audio_out[i] = 0.0

                proc.process_block(ctxt, None)  # TODO: pass time_mapper
                if proc.state == processor.State.BROKEN:
                    break

            self.assertEqual(proc.state, processor.State.BROKEN)

            proc.cleanup()

        finally:
            fake_host_quit.set()
            fake_host_thread.join()
