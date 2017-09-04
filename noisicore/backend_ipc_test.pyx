from libcpp.memory cimport unique_ptr

from .buffers cimport *
from .status cimport *
from .vm cimport *
from .backend cimport *
from .host_data cimport *

import os
import os.path
import struct
import tempfile
import uuid
import unittest
import threading

import capnp

from . import audio_stream
from . import block_data_capnp


cdef _check(const Status& status):
    if status.is_connection_closed():
        raise audio_stream.ConnectionClosed

    if status.is_error():
        raise audio_stream.Error(status.message())


class TestIPCBackend(unittest.TestCase):
    def test_foo(self):
        cdef Status status
        cdef float samples[128]

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef unique_ptr[VM] vm
        vm.reset(new VM(host_data.get()))

        cdef BackendSettings backend_settings
        backend_settings.ipc_address = os.fsencode(
            os.path.join(
                tempfile.gettempdir(),
                'test.%s.pipe' % uuid.uuid4().hex))

        cdef unique_ptr[Backend] beptr
        beptr.reset(Backend.create(b"ipc", backend_settings))

        cdef Backend* be = beptr.get()
        status = be.setup(vm.get())
        self.assertFalse(status.is_error(), status.message())

        def backend_thread():
            cdef Status status
            cdef float buf[4]

            try:
                while True:
                    with nogil:
                        status = be.begin_block()
                    _check(status)

                    buf[0:4] = [0.0, 0.5, 1.0, 0.5]
                    _check(be.output(b"left", <BufferPtr>buf))

                    buf[0:4] = [0.0, -0.5, -1.0, -0.5]
                    _check(be.output(b"right", <BufferPtr>buf))

                    with nogil:
                        status = be.end_block()
                    _check(status)

            except audio_stream.ConnectionClosed:
                pass

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
