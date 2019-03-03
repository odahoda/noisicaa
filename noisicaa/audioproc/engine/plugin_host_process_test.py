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
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa import node_db
from noisicaa.audioproc.public import plugin_state_pb2
from noisicaa.audioproc import audioproc_pb2
from . import plugin_host_pb2
from . import plugin_host

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow):
    closed = QtCore.pyqtSignal()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class PluginHostProcessTest(
        unittest_mixins.ServerMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest_engine_mixins.HostSystemMixin,
        qttest.QtTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.shm = None
        self.shm_data = None
        self.cb_endpoint = None
        self.cb_endpoint_address = None

    async def setup_testcase(self):
        self.done = asyncio.Event(loop=self.loop)

        self.shm = posix_ipc.SharedMemory(
            name='/test-shm-%s' % uuid.uuid4().hex,
            flags=os.O_CREAT | os.O_EXCL,
            size=2**20)

        self.shm_data = mmap.mmap(self.shm.fd, self.shm.size)

        self.cb_endpoint = ipc.ServerEndpoint('project_cb')
        self.cb_endpoint_address = await self.server.add_endpoint(self.cb_endpoint)

        self.setup_urid_mapper_process(inline=False)

    async def cleanup_testcase(self):
        if self.cb_endpoint_address is not None:
            await self.server.remove_endpoint('project_cb')

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
        proc, stub = await self.create_process(inline=True)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'
            block_size = 256

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])

            create_plugin_request = plugin_host_pb2.CreatePluginRequest(
                spec=spec,
                callback_address=self.cb_endpoint_address)
            create_plugin_response = plugin_host_pb2.CreatePluginResponse()
            await stub.call(
                'CREATE_PLUGIN', create_plugin_request, create_plugin_response)
            pipe_path = create_plugin_response.pipe_path

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

            await stub.call(
                'DELETE_PLUGIN',
                plugin_host_pb2.DeletePluginRequest(realm='root', node_id='1234'))

        finally:
            await stub.close()
            await proc.shutdown()

    async def test_save_state(self):
        self.host_system.set_block_size(256)

        done = asyncio.Event(loop=self.loop)

        def plugin_state_change(request, response):
            self.assertEqual(request.realm, 'root')
            self.assertEqual(request.node_id, '1234')
            self.assertIsInstance(request.state, plugin_state_pb2.PluginState)
            done.set()
        self.cb_endpoint.add_handler(
            'PLUGIN_STATE_CHANGE', plugin_state_change,
            audioproc_pb2.PluginStateChange, empty_message_pb2.EmptyMessage)

        proc, stub = await self.create_process(inline=True)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-state'
            node_desc = self.node_db[plugin_uri]

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(node_desc)

            create_plugin_request = plugin_host_pb2.CreatePluginRequest(
                spec=spec,
                callback_address=self.cb_endpoint_address)
            create_plugin_response = plugin_host_pb2.CreatePluginResponse()
            await stub.call(
                'CREATE_PLUGIN', create_plugin_request, create_plugin_response)
            pipe_path = create_plugin_response.pipe_path

            with open(pipe_path, 'wb', buffering=0):
                await asyncio.wait_for(done.wait(), 10, loop=self.loop)

            await stub.call(
                'DELETE_PLUGIN',
                plugin_host_pb2.DeletePluginRequest(realm='root', node_id='1234'))

        finally:
            await stub.close()
            await proc.shutdown()

    @unittest.skipUnless(TEST_OPTS.ALLOW_UI, "Requires UI")
    async def test_create_ui(self):
        done = asyncio.Event(loop=self.loop)

        win = Window()
        win.closed.connect(done.set)

        def control_value_change(request, response):
            self.assertEqual(request.realm, 'root')
            self.assertEqual(request.node_id, '1234')
            self.assertEqual(request.value.name, 'ctrl')
            if request.value.value >= 1.0:
                done.set()
        self.cb_endpoint.add_handler(
            'CONTROL_VALUE_CHANGE', control_value_change,
            audioproc_pb2.ControlValueChange, empty_message_pb2.EmptyMessage)

        proc, stub = await self.create_process(inline=False)
        try:
            plugin_uri = 'http://noisicaa.odahoda.de/plugins/test-ui-gtk2'

            spec = plugin_host_pb2.PluginInstanceSpec()
            spec.realm = 'root'
            spec.node_id = '1234'
            spec.node_description.CopyFrom(self.node_db[plugin_uri])

            create_plugin_request = plugin_host_pb2.CreatePluginRequest(
                spec=spec,
                callback_address=self.cb_endpoint_address)
            create_plugin_response = plugin_host_pb2.CreatePluginResponse()
            await stub.call(
                'CREATE_PLUGIN', create_plugin_request, create_plugin_response)

            create_ui_request = plugin_host_pb2.CreatePluginUIRequest(
                realm='root', node_id='1234')
            create_ui_response = plugin_host_pb2.CreatePluginUIResponse()
            await stub.call('CREATE_UI', create_ui_request, create_ui_response)
            wid = create_ui_response.wid
            size = (create_ui_response.width, create_ui_response.height)

            # fromWinId expects some 'voidptr'...
            proxy_win = QtGui.QWindow.fromWinId(wid)  # type: ignore
            proxy_widget = QtWidgets.QWidget.createWindowContainer(proxy_win, win)
            proxy_widget.setMinimumSize(*size)
            #proxy_widget.setMaximumSize(*size)

            win.setCentralWidget(proxy_widget)
            win.resize(*size)
            win.show()

            await asyncio.wait_for(done.wait(), 10, loop=self.loop)

            win.hide()

            await stub.call(
                'DELETE_UI',
                plugin_host_pb2.CreatePluginUIRequest(realm='root', node_id='1234'))

            await stub.call(
                'DELETE_PLUGIN',
                plugin_host_pb2.DeletePluginRequest(realm='root', node_id='1234'))

        finally:
            await stub.close()
            await proc.shutdown()
