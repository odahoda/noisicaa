import os
import os.path
import uuid
import tempfile
import unittest
import threading

from . import audio_stream


class TestAudioStream(unittest.TestCase):
    def setUp(self):
        self.address = os.fsencode(
            os.path.join(
                tempfile.gettempdir(),
                'test.%s.pipe' % uuid.uuid4().hex))

    def test_client_to_server(self):
        server = audio_stream.AudioStream.create_server(self.address)
        server.setup()

        client = audio_stream.AudioStream.create_client(self.address)
        client.setup()

        def server_thread():
            request = server.receive_bytes()
            server.send_bytes(request)

        thread = threading.Thread(target=server_thread)
        thread.start()

        request = b'123' * 100000
        client.send_bytes(request)
        response = client.receive_bytes()

        self.assertEqual(response, b'123' * 100000)

        client.cleanup()
        server.cleanup()
