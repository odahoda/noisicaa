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

# TODO: mypy-unclean

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
from noisicaa.constants import TEST_OPTS
from noisicaa import audioproc
from noisicaa.core import ipc
from noisicaa import node_db
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
        unittest.QtTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.done = None
        self.shm = None
        self.shm_data = None
        self.audioproc_server = None

    async def setup_testcase(self):
        self.done = asyncio.Event(loop=self.loop)

        self.shm = posix_ipc.SharedMemory(
            name='/test-shm-%s' % uuid.uuid4().hex,
            flags=os.O_CREAT | os.O_EXCL,
            size=2**20)

        self.shm_data = mmap.mmap(self.shm.fd, self.shm.size)

        self.setup_urid_mapper_process(inline=False)

        self.audioproc_server = ipc.Server(
            name='audioproc',
            event_loop=self.loop,
            socket_dir=TEST_OPTS.TMP_DIR)
        self.audioproc_server.add_command_handler('START_SESSION', self.audioproc_start_session)
        self.audioproc_server.add_command_handler('END_SESSION', self.audioproc_end_session)
        self.audioproc_server.add_command_handler(
            'PIPELINE_MUTATION', self.audioproc_pipeline_mutation)
        await self.audioproc_server.setup()

    async def cleanup_testcase(self):
        if self.audioproc_server is not None:
            await self.audioproc_server.cleanup()
            self.audioproc_server = None

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
                entry='noisicaa.audioproc.engine.plugin_host_process.PluginHostProcess',
                audioproc_address=self.audioproc_server.address)
        else:
            proc = await self.process_manager.start_subprocess(
                'test-plugin-host',
                'noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess',
                audioproc_address=self.audioproc_server.address)

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect()
        return proc, stub

    def audioproc_start_session(self, callback_address, flags):
        return 'session-id-123'

    def audioproc_end_session(self, session_id):
        self.assertEqual(session_id, 'session-id-123')

    def audioproc_pipeline_mutation(self, session_id, realm, mutation):
        self.assertEqual(session_id, 'session-id-123')
        self.assertEqual(realm, 'root')
        self.assertIsInstance(mutation, audioproc.SetControlValue)
        self.assertIsInstance(mutation.value, float)
        self.assertEqual(mutation.name, '1234:ctrl')
        if mutation.value >= 1.0:
            self.done.set()

    async def test_create_plugin(self):
        _, stub = await self.create_process(inline=True)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'
            block_size = 256

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])
            pipe_path = await stub.call('CREATE_PLUGIN', spec)

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
                    bufp[port_spec.name] = p.cast('f')
                elif port_spec.type == node_db.PortDescription.KRATE_CONTROL:
                    bufp[port_spec.name] = p.cast('f')
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

    @unittest.skip("health checks don't work as intended.")
    async def test_audioproc_dies(self):
        proc, stub = await self.create_process(inline=False)
        try:
            await self.audioproc_server.cleanup()
            self.audioproc_server = None

            await proc.wait()

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()

    @unittest.skipUnless(TEST_OPTS.ALLOW_UI, "Requires UI")
    async def test_create_ui(self):
        win = Window()
        win.closed.connect(self.done.set)

        _, stub = await self.create_process(inline=False)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])
            await stub.call('CREATE_PLUGIN', spec)

            wid, size = await stub.call('CREATE_UI', 'root', '1234')

            proxy_win = QtGui.QWindow.fromWinId(wid)
            proxy_widget = QtWidgets.QWidget.createWindowContainer(proxy_win, win)
            proxy_widget.setMinimumSize(*size)
            #proxy_widget.setMaximumSize(*size)

            win.setCentralWidget(proxy_widget)
            win.resize(*size)
            win.show()

            await asyncio.wait_for(self.done.wait(), 10, loop=self.loop)

            win.hide()

            await stub.call('DELETE_UI', 'root', '1234')

            await stub.call('DELETE_PLUGIN', 'root', '1234')

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()
