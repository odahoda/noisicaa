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
import mmap
import os
import uuid

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import posix_ipc

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import qttest
from noisicaa.constants import TEST_OPTS
from noisicaa.core import ipc
from noisicaa import node_db
from noisicaa.audioproc.public import plugin_state_pb2
from . import plugin_host_pb2
from . import plugin_host

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow):
    closed = QtCore.pyqtSignal()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class PluginHostProcessTest(
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest_engine_mixins.HostSystemMixin,
        qttest.QtTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.shm = None
        self.shm_data = None
        self.project_server = None

    async def setup_testcase(self):
        self.done = asyncio.Event(loop=self.loop)

        self.shm = posix_ipc.SharedMemory(
            name='/test-shm-%s' % uuid.uuid4().hex,
            flags=os.O_CREAT | os.O_EXCL,
            size=2**20)

        self.shm_data = mmap.mmap(self.shm.fd, self.shm.size)

        self.project_server = ipc.Server(
            name='project',
            event_loop=self.loop,
            socket_dir=TEST_OPTS.TMP_DIR)
        await self.project_server.setup()

        self.setup_urid_mapper_process(inline=False)

    async def cleanup_testcase(self):
        if self.project_server is not None:
            await self.project_server.cleanup()

        if self.shm_data is not None:
            self.shm_data.close()
            self.shm_data = None

        if self.shm is not None:
            self.shm.close_fd()
            self.shm.unlink()
            self.shm = None

    async def create_process(self, *, inline):
        if inline:
            proc = await self.process_manager.start_inline_process(
                name='test-plugin-host',
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostProcess')
        else:
            proc = await self.process_manager.start_subprocess(
                'test-plugin-host',
                'noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess')

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect()
        return proc, stub

    async def test_create_plugin(self):
        _, stub = await self.create_process(inline=True)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'
            block_size = 256

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])
            pipe_path = await stub.call('CREATE_PLUGIN', spec, self.project_server.address)

            pipe = open(pipe_path, 'wb', buffering=0)

            shm_data = memoryview(self.shm_data)
            offset = 0

            bufp = {}
            buffers = []
            for port_index, port_spec in enumerate(spec.node_description.ports):
                if port_spec.type == node_db.PortDescription.AUDIO:
                    bufsize = block_size * 4
                elif port_spec.type == node_db.PortDescription.KRATE_CONTROL:
                    bufsize = 4
                else:
                    raise ValueError(port_spec.type)

                buffers.append((port_index, offset))

                p = shm_data[offset:offset+bufsize]
                if port_spec.type == node_db.PortDescription.AUDIO:
                    # TODO: mypy doesn't know memoryview.cast
                    bufp[port_spec.name] = p.cast('f')  # type: ignore
                elif port_spec.type == node_db.PortDescription.KRATE_CONTROL:
                    # TODO: mypy doesn't know memoryview.cast
                    bufp[port_spec.name] = p.cast('f')  # type: ignore
                else:
                    raise ValueError(port_spec.type)

                offset += bufsize

            cond_offset = offset
            offset = plugin_host.init_cond(shm_data, offset)
            assert offset < self.shm.size

            memmap = plugin_host.build_memory_mapping(
                self.shm.name,
                cond_offset,
                block_size,
                buffers)
            pipe.write(b'MEMORY_MAP\n')
            pipe.write(b'%d\n' % len(memmap))
            pipe.write(memmap)

            for i in range(10):
                for s in range(block_size):
                    bufp['audio_in'][s] = i / 9.0
                    bufp['audio_out'][s] = 0.0
                bufp['ctrl'][0] = 0.5

                plugin_host.cond_clear(shm_data, cond_offset)
                pipe.write(b'PROCESS_BLOCK\n')
                plugin_host.cond_wait(shm_data, cond_offset)

                for s in range(block_size):
                    self.assertAlmostEqual(bufp['audio_out'][s], 0.5 * i / 9.0, places=2)

            pipe.close()

            await stub.call('DELETE_PLUGIN', 'root', '1234')

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()

    async def test_save_state(self):
        self.host_system.set_block_size(256)

        done = asyncio.Event(loop=self.loop)

        def plugin_state_change(realm, node_id, state):
            self.assertEqual(realm, 'root')
            self.assertEqual(node_id, '1234')
            self.assertIsInstance(state, plugin_state_pb2.PluginState)
            done.set()
        self.project_server.add_command_handler('PLUGIN_STATE_CHANGE', plugin_state_change)

        _, stub = await self.create_process(inline=True)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-state'
            node_desc = self.node_db[plugin_uri]

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(node_desc)
            pipe_path = await stub.call('CREATE_PLUGIN', spec, self.project_server.address)

            with open(pipe_path, 'wb', buffering=0):
                await asyncio.wait_for(done.wait(), 10, loop=self.loop)

            await stub.call('DELETE_PLUGIN', 'root', '1234')

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()

    @unittest.skipUnless(TEST_OPTS.ALLOW_UI, "Requires UI")
    async def test_create_ui(self):
        done = asyncio.Event(loop=self.loop)

        win = Window()
        win.closed.connect(done.set)

        def control_value_change(realm, node_id, port_name, value, generation):
            self.assertEqual(realm, 'root')
            self.assertEqual(node_id, '1234')
            self.assertEqual(port_name, 'ctrl')
            self.assertIsInstance(value, float)
            if value >= 1.0:
                done.set()
        self.project_server.add_command_handler('CONTROL_VALUE_CHANGE', control_value_change)

        _, stub = await self.create_process(inline=False)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])
            await stub.call('CREATE_PLUGIN', spec, self.project_server.address)

            wid, size = await stub.call('CREATE_UI', 'root', '1234')

            proxy_win = QtGui.QWindow.fromWinId(wid)
            proxy_widget = QtWidgets.QWidget.createWindowContainer(proxy_win, win)
            proxy_widget.setMinimumSize(*size)
            #proxy_widget.setMaximumSize(*size)

            win.setCentralWidget(proxy_widget)
            win.resize(*size)
            win.show()

            await asyncio.wait_for(done.wait(), 10, loop=self.loop)

            win.hide()

            await stub.call('DELETE_UI', 'root', '1234')

            await stub.call('DELETE_PLUGIN', 'root', '1234')

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()
