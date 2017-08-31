from libcpp.memory cimport unique_ptr

from .audio_stream cimport *
from .status cimport *

import os
import os.path
import uuid
import tempfile
import unittest
import threading

class TestAudioStream(unittest.TestCase):
    def setUp(self):
        self.address = os.fsencode(
            os.path.join(
                tempfile.gettempdir(),
                'test.%s.pipe' % uuid.uuid4().hex))

    def test_client_to_server(self):
        cdef Status status

        cdef unique_ptr[AudioStreamBase] server_ptr
        server_ptr.reset(new AudioStreamServer(self.address))
        cdef AudioStreamBase* server = server_ptr.get()
        status = server.setup()
        self.assertFalse(status.is_error(), status.message())

        cdef unique_ptr[AudioStreamBase] client_ptr
        client_ptr.reset(new AudioStreamClient(self.address))
        cdef AudioStreamBase* client = client_ptr.get()
        status = client.setup()
        self.assertFalse(status.is_error(), status.message())

        def server_thread():
            cdef StatusOr[string] status_or_request
            with nogil:
                status_or_request = server.receive_frame_bytes()
            self.assertFalse(
                status_or_request.is_error(), status_or_request.message())
            cdef string request = status_or_request.result()
            with nogil:
                server.send_frame_bytes(request)

        thread = threading.Thread(target=server_thread)
        thread.start()

        cdef string request = b'123' * 100000
        with nogil:
            status = client.send_frame_bytes(request)
        self.assertFalse(status.is_error(), status.message())

        cdef StatusOr[string] status_or_response
        with nogil:
            status_or_response = client.receive_frame_bytes()
        self.assertFalse(status_or_response.is_error(), status_or_response.message())
        response = status_or_response.result()

        self.assertEqual(response, b'123' * 100000)

