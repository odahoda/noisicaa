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

# TODO: mypy-unclean

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
from . import plugin_host_pb2
from . import block_context
from . import buffers
from . import processor
from . import processor_pb2
from . import buffer_arena

logger = logging.getLogger(__name__)


class ProcessorPluginTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.audioproc_server = None

    async def setup_testcase(self):
        self.setup_urid_mapper_process(inline=True)

        self.audioproc_server = ipc.Server(self.loop, 'audioproc', TEST_OPTS.TMP_DIR)
        self.audioproc_server.add_command_handler('START_SESSION', self.audioproc_start_session)
        self.audioproc_server.add_command_handler('END_SESSION', self.audioproc_end_session)
        await self.audioproc_server.setup()

    async def cleanup_testcase(self):
        if self.audioproc_server is not None:
            await self.audioproc_server.cleanup()

    def audioproc_start_session(self, callback_address, flags):
        return 'session-123'

    def audioproc_end_session(self, session_id):
        assert session_id == 'session-123'

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_process(self, *, inline_plugin_host=True):
        if inline_plugin_host:
            proc = await self.process_manager.start_inline_process(
                name='plugin_host',
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostProcess',
                audioproc_address=self.audioproc_server.address)
        else:
            proc = await self.process_manager.start_subprocess(
                name='plugin_host',
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess',
                audioproc_address=self.audioproc_server.address)

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect()
        try:
            await async_generator.yield_(stub)
        finally:
            await stub.call('SHUTDOWN')
            await stub.close()

            await proc.wait()

    async def test_plugin(self):
        async with self.create_process() as plugin_host:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-passthru'
            node_desc = self.node_db[plugin_uri]

            plugin_spec = plugin_host_pb2.PluginInstanceSpec()
            plugin_spec.realm = 'root'
            plugin_spec.node_id = '1234'
            plugin_spec.node_description.CopyFrom(node_desc)
            pipe_address = await plugin_host.call('CREATE_PLUGIN', plugin_spec)

            proc = processor.PyProcessor('test_node', self.host_system, node_desc)
            proc.setup()
            proc.set_parameters(
                processor_pb2.ProcessorParameters(
                    plugin_pipe_path=os.fsencode(pipe_address)))

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

            await plugin_host.call('DELETE_PLUGIN', plugin_spec.realm, plugin_spec.node_id)

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
            cond_type = buffer_mgr.type('plugin_cond')
            cond_buf = buffer_mgr['plugin_cond']
            cond_type.set_cond(cond_buf)

            logger.info("Fake host finished.")

        fake_host_thread = threading.Thread(target=fake_host)
        fake_host_thread.start()
        try:
            fake_host_ready.wait()

            proc = processor.PyProcessor('test_node', self.host_system, node_desc)
            proc.setup()
            proc.set_parameters(
                processor_pb2.ProcessorParameters(
                    plugin_pipe_path=os.fsencode(pipe_address)))

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

            proc = processor.PyProcessor('test_node', self.host_system, node_desc)
            proc.setup()
            proc.set_parameters(
                processor_pb2.ProcessorParameters(
                    plugin_pipe_path=os.fsencode(pipe_address)))

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
