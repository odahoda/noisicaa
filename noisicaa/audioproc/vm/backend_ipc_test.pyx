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

from libcpp.memory cimport unique_ptr

import os
import os.path
import struct
import tempfile
import uuid
import threading

import capnp

from noisidev import unittest
from noisicaa.core.status cimport *
from noisicaa.core.status import *
from . import audio_stream
from . import block_data_capnp
from .buffers cimport *
from .vm cimport *
from .backend cimport *
from .host_data cimport *


class TestIPCBackend(unittest.TestCase):
    def test_foo(self):
        cdef Status status
        cdef float samples[128]

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef unique_ptr[VM] vm
        vm.reset(new VM(host_data.get(), NULL))

        cdef PyBackendSettings backend_settings = PyBackendSettings(
            ipc_address=os.path.join(
                tempfile.gettempdir(),
                'test.%s.pipe' % uuid.uuid4().hex))

        cdef StatusOr[Backend*] stor_backend = Backend.create(b"ipc", backend_settings.get())
        check(stor_backend)
        cdef unique_ptr[Backend] beptr
        beptr.reset(stor_backend.result())

        cdef Backend* be = beptr.get()
        status = be.setup(vm.get())
        self.assertFalse(status.is_error(), status.message())

        def backend_thread():
            cdef Status status
            cdef float buf[4]
            cdef PyBlockContext ctxt = PyBlockContext()

            while True:
                with nogil:
                    check(be.begin_block(ctxt.get()))

                if be.stopped():
                    break

                buf[0:4] = [0.0, 0.5, 1.0, 0.5]
                check(be.output(ctxt.get(), b"left", <BufferPtr>buf))

                buf[0:4] = [0.0, -0.5, -1.0, -0.5]
                check(be.output(ctxt.get(), b"right", <BufferPtr>buf))

                with nogil:
                    check(be.end_block(ctxt.get()))

        thread = threading.Thread(target=backend_thread)
        thread.start()

        client = audio_stream.AudioStream.create_client(backend_settings.ipc_address)
        client.setup()

        request = block_data_capnp.BlockData.new_message();
        request.blockSize = 4;
        request.samplePos = 4096;
        client.send_bytes(request.to_bytes())

        response_bytes = client.receive_bytes()
        response = block_data_capnp.BlockData.from_bytes(response_bytes)

        self.assertEqual(response.blockSize, 4)
        self.assertEqual(response.samplePos, 4096)
        self.assertEqual(len(response.buffers), 2)
        self.assertEqual(response.buffers[0].id, 'output:0')
        self.assertEqual(response.buffers[0].data, struct.pack('ffff', 0.0, 0.5, 1.0, 0.5))
        self.assertEqual(response.buffers[1].id, 'output:1')
        self.assertEqual(response.buffers[1].data, struct.pack('ffff', 0.0, -0.5, -1.0, -0.5))

        client.cleanup()

        thread.join()

        be.cleanup()
