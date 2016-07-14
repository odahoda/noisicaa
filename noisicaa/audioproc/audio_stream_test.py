#!/usr/bin/python3

import os.path
import tempfile
import threading
import unittest
import uuid

from . import audio_stream


class AudioStreamSTest(unittest.TestCase):
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

                data = server.receive_frame()
                data.timepos += 1
                server.send_frame(data)

            finally:
                server.cleanup()

        thread = threading.Thread(target=server_thread)
        thread.start()
        server_ready.wait()

        client = audio_stream.AudioStreamClient(address)
        try:
            client.setup()

            data = audio_stream.FrameData()
            data.timepos = 1234
            data.samples = b'pling'
            data.num_samples = 3
            data.events = [('q1', 'event1'), ('q2', 'event2')]
            client.send_frame(data)

            data = client.receive_frame()
            self.assertEqual(data.timepos, 1235)
            self.assertEqual(data.samples, b'pling')
            self.assertEqual(data.num_samples, 3)
            self.assertEqual(
                data.events, [('q1', 'event1'), ('q2', 'event2')])

        finally:
            client.cleanup()


if __name__ == '__main__':
    unittest.main()
