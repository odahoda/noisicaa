# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

import unittest
import sys
import threading
import uuid
import os
import os.path
import tempfile
import struct

import capnp

from noisicaa.core.status cimport *
from noisicaa.core.status import ConnectionClosed
from . import block_data_capnp
from . import audio_stream
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *


class TestProcessorIPC(unittest.TestCase):
    def test_ipc(self):
        cdef Status status

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        address = os.fsencode(
            os.path.join(
                tempfile.gettempdir(),
                'test.%s.pipe' % uuid.uuid4().hex))

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'ipc')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())

        server = audio_stream.AudioStream.create_server(address)
        server.setup()

        def server_thread():
            try:
                while True:
                    request_bytes = server.receive_bytes()
                    request = block_data_capnp.BlockData.from_bytes(request_bytes)

                    response = block_data_capnp.BlockData.new_message()
                    response.blockSize = request.blockSize
                    response.samplePos = request.samplePos
                    response.init('buffers', 2)
                    b = response.buffers[0]
                    b.id = 'output:0'
                    b.data = struct.pack('ffff', 0.0, 0.5, 1.0, 0.5)
                    b = response.buffers[1]
                    b.id = 'output:1'
                    b.data = struct.pack('ffff', 0.0, -0.5, -1.0, -0.5)

                    response_bytes = response.to_bytes()
                    server.send_bytes(response_bytes)

            except ConnectionClosed:
                pass

        thread = threading.Thread(target=server_thread)
        thread.start()

        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'left', PortType.audio, PortDirection.Output)
        spec.get().add_port(b'right', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'ipc_address', address))

        check(processor.setup(spec.release()))

        cdef float leftbuf[4]
        cdef float rightbuf[4]

        check(processor.connect_port(0, <BufferPtr>leftbuf))
        check(processor.connect_port(1, <BufferPtr>rightbuf))

        for i in range(4):
            leftbuf[i] = 0.0
            rightbuf[i] = 0.0

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 4
        ctxt.sample_pos = 1024

        with nogil:
            status = processor.run(ctxt.get(), NULL)  # TODO: pass time_mapper
        check(status)

        self.assertEqual(leftbuf, [0.0, 0.5, 1.0, 0.5])
        self.assertEqual(rightbuf, [0.0, -0.5, -1.0, -0.5])

        processor.cleanup()

        thread.join()
        server.cleanup()
