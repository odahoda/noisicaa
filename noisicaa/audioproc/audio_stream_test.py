#!/usr/bin/python3

import os.path
import tempfile
import threading
import unittest
import uuid

from . import audio_stream
from . import data


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

                frame = server.receive_frame()
                frame.sample_pos += 1
                server.send_frame(frame)

            finally:
                server.cleanup()

        thread = threading.Thread(target=server_thread)
        thread.start()
        server_ready.wait()

        client = audio_stream.AudioStreamClient(address)
        try:
            client.setup()

            frame = data.FrameData()
            frame.sample_pos = 1234
            frame.duration = 32
            frame.samples = b'pling'
            frame.num_samples = 3
            frame.events = [('q1', 'event1'), ('q2', 'event2')]
            client.send_frame(frame)

            frame = client.receive_frame()
            self.assertEqual(frame.sample_pos, 1235)
            self.assertEqual(frame.samples, b'pling')
            self.assertEqual(frame.num_samples, 3)
            self.assertEqual(
                frame.events, [('q1', 'event1'), ('q2', 'event2')])

        finally:
            client.cleanup()


if __name__ == '__main__':
    unittest.main()
