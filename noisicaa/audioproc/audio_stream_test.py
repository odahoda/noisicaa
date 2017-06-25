#!/usr/bin/python3

import os.path
import tempfile
import threading
import unittest
import uuid

from . import audio_stream
from . import frame_data_capnp


class AudioStreamTest(unittest.TestCase):
    def test_client_to_server(self):
        address = os.path.join(
            tempfile.gettempdir(),
            'test.%s.pipe' % uuid.uuid4().hex)
        server_ready = threading.Event()

        def server_thread():
            server = audio_stream.AudioStreamServer(address)
            try:
                server.setup()
                server_ready.set()

                request = server.receive_frame()
                response = frame_data_capnp.FrameData.new_message()
                response.samplePos = request.samplePos + 1
                response.frameSize = request.frameSize
                server.send_frame(response)

            finally:
                server.cleanup()

        thread = threading.Thread(target=server_thread)
        thread.start()
        server_ready.wait()

        client = audio_stream.AudioStreamClient(address)
        try:
            client.setup()

            request = frame_data_capnp.FrameData.new_message()
            request.samplePos = 1234
            request.frameSize = 32
            client.send_frame(request)

            response = client.receive_frame()
            self.assertEqual(response.samplePos, 1235)
            self.assertEqual(response.frameSize, 32)

        finally:
            client.cleanup()


if __name__ == '__main__':
    unittest.main()
