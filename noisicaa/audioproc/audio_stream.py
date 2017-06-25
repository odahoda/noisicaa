#!/usr/bin/python3

import logging
import os.path
import pickle
import select
import threading
import uuid

import capnp

from . import frame_data_capnp

logger = logging.getLogger(__name__)


class StreamClosed(Exception):
    pass

class StreamError(Exception):
    pass


class AudioStreamBase(object):
    def __init__(self, address):
        assert address is not None
        self._address = address

        self._pipe_in = None
        self._pipe_out = None
        self._poller = None

        self._closed = False
        self._buffer = bytearray()

    @property
    def address(self):
        return self._address

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

    def receive_frame_bytes(self):
        line = self._get_line()
        if line == b'#CLOSE':
            raise StreamClosed

        assert line.startswith(b'#FR='), line
        payload = self._get_bytes(int(line[4:]))

        line = self._get_line()
        assert line == b'#END', line

        return payload

    def receive_frame(self):
        return frame_data_capnp.FrameData.from_bytes_packed(
            self.receive_frame_bytes())

    def send_frame_bytes(self, frame_bytes):
        request = bytearray()
        request.extend(b'#FR=%d\n' % len(frame_bytes))
        request.extend(frame_bytes)
        request.extend(b'#END\n')

        while request:
            written = os.write(self._pipe_out, request)
            del request[:written]

    def send_frame(self, frame):
        self.send_frame_bytes(frame.to_bytes_packed())


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

        if self._pipe_out is not None:
            request = bytearray()
            request.extend(b'#CLOSE\n')
            while request:
                written = os.write(self._pipe_out, request)
                del request[:written]

            os.close(self._pipe_out)
            self._pipe_out = None

        if self._pipe_in is not None:
            os.close(self._pipe_in)
            self._pipe_in = None
