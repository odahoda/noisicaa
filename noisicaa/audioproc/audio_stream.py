#!/usr/bin/python3

import logging
import os.path
import pickle
import select
import threading
import uuid

from . import data

logger = logging.getLogger(__name__)


class StreamClosed(Exception):
    pass

class StreamError(Exception):
    pass


class AudioStreamBase(object):
    def __init__(self, address):
        self._address = address

        self._pipe_in = None
        self._pipe_out = None
        self._poller = None

        self._closed = False
        self._buffer = bytearray()

    def setup(self):
        self._poller = select.poll()
        self._poller.register(self._pipe_in, select.POLLIN)

    def cleanup(self):
        if self._poller is not None:
            self._poller.unregister(self._pipe_in)
            self._poller = None

        self._buffer.clear()

    def close(self):
        self._closed = True

    def _fill_buffer(self):
        while True:
            for fd, event in self._poller.poll(0.5):
                assert fd == self._pipe_in

                if event & select.POLLIN:
                    dat = os.read(self._pipe_in, 1024)
                    #logger.info("dat=%s", dat)
                    self._buffer.extend(dat)
                    return

                elif event & select.POLLHUP:
                    logger.warning("Pipe disconnected")
                    raise StreamClosed

                else:
                    raise StreamError("Unknown event %s" % event)

            if self._closed:
                raise StreamClosed("Stream closed")

    def _get_line(self):
        while True:
            eol = self._buffer.find(b'\n')
            if eol >= 0:
                line = self._buffer[:eol]
                del self._buffer[:eol+1]
                return line

            self._fill_buffer()

    def _get_bytes(self, num_bytes):
        while len(self._buffer) < num_bytes:
            self._fill_buffer()

        d = self._buffer[:num_bytes]
        del self._buffer[:num_bytes]
        return d

    def receive_frame(self):
        frame = data.FrameData()
        frame.events = []
        frame.entities = {}
        frame.perf_data = []

        line = self._get_line()
        assert line.startswith(b'#FR=')
        frame.sample_pos = int(line[4:])
        while True:
            line = self._get_line()
            if line == b'#END':
                break

            elif line.startswith(b'DURATION='):
                frame.duration = int(line[9:])

            elif line.startswith(b'EVENT='):
                queue = line[6:].decode('utf-8')

                length = self._get_line()
                assert length.startswith(b'LEN=')
                serialized = self._get_bytes(int(length[4:]))
                event = pickle.loads(serialized)
                frame.events.append((queue, event))

            elif line.startswith(b'ENTITY='):
                name = line[7:].decode('utf-8')

                length = self._get_line()
                assert length.startswith(b'LEN=')
                serialized = self._get_bytes(int(length[4:]))
                entity = data.Entity.deserialize(serialized)
                frame.entities[name] = entity

            elif line.startswith(b'SAMPLES='):
                frame.num_samples = int(line[8:])

                line = self._get_line()
                assert line.startswith(b'LEN=')
                num_bytes = int(line[4:])

                frame.samples = self._get_bytes(num_bytes)
                assert len(frame.samples) == num_bytes

            elif line.startswith(b'PERF='):
                serialized = self._get_bytes(int(line[5:]))
                span = pickle.loads(serialized)
                frame.perf_data.append(span)

            else:
                raise StreamError("Unexpected token %r" % line)

        return frame

    def send_frame(self, frame):
        request = bytearray()
        request.extend(b'#FR=%d\n' % frame.sample_pos)
        request.extend(b'DURATION=%d\n' % frame.duration)

        if frame.events:
            for queue, event in frame.events:
                request.extend(b'EVENT=%s\n' % queue.encode('utf-8'))
                serialized = pickle.dumps(event)
                request.extend(b'LEN=%d\n' % len(serialized))
                request.extend(serialized)

        if frame.entities:
            for name, entity in frame.entities.items():
                request.extend(b'ENTITY=%s\n' % name.encode('utf-8'))
                serialized = entity.serialize()
                request.extend(b'LEN=%d\n' % len(serialized))
                request.extend(serialized)

        if frame.samples:
            request.extend(b'SAMPLES=%d\n' % frame.num_samples)
            request.extend(b'LEN=%d\n' % len(frame.samples))
            request.extend(frame.samples)

        for span in frame.perf_data or []:
            serialized = pickle.dumps(span)
            request.extend(b'PERF=%d\n' % len(serialized))
            request.extend(serialized)

        request.extend(b'#END\n')

        while request:
            written = os.write(self._pipe_out, request)
            del request[:written]


class AudioStreamServer(AudioStreamBase):
    def __init__(self, address):
        super().__init__(address)

    def setup(self):
        logger.info("Serving from %s", self._address)

        os.mkfifo(self._address + '.send')
        self._pipe_in = os.open(
            self._address + '.send', os.O_RDONLY | os.O_NONBLOCK)
        os.set_blocking(self._pipe_in, True)

        os.mkfifo(self._address + '.recv')
        self._pipe_out = os.open(
            self._address + '.recv', os.O_RDWR | os.O_NONBLOCK)
        os.set_blocking(self._pipe_out, True)

        super().setup()

        logger.info("Server ready.")

    def cleanup(self):
        super().cleanup()
        if self._pipe_in is not None:
            os.close(self._pipe_in)
            self._pipe_in = None

        if self._pipe_out is not None:
            os.close(self._pipe_out)
            self._pipe_out = None

        if os.path.exists(self._address + '.send'):
            os.unlink(self._address + '.send')

        if os.path.exists(self._address + '.recv'):
            os.unlink(self._address + '.recv')


class AudioStreamClient(AudioStreamBase):
    def __init__(self, address):
        super().__init__(address)

    def setup(self):
        logger.info("Connecting to %s...", self._address)
        self._pipe_in = os.open(
            self._address + '.recv', os.O_RDONLY | os.O_NONBLOCK)
        os.set_blocking(self._pipe_in, True)

        self._pipe_out = os.open(
            self._address + '.send', os.O_RDWR | os.O_NONBLOCK)
        os.set_blocking(self._pipe_out, True)

        super().setup()

    def cleanup(self):
        super().cleanup()

        if self._pipe_in is not None:
            os.close(self._pipe_in)
            self._pipe_in = None

        if self._pipe_out is not None:
            os.close(self._pipe_out)
            self._pipe_out = None
