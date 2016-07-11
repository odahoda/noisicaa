#!/usr/bin/python3

import asyncio
import logging
import os
import pickle
import random
import threading

from noisicaa.core import ipc
from noisicaa import music

from .. import ports
from .. import node
from .. import frame
from .. import node_types
from .. import events

logger = logging.getLogger(__name__)


class IPCNode(node.Node):
    desc = node_types.NodeType()
    desc.name = 'ipc'
    desc.parameter('address', 'string')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, address):
        super().__init__(event_loop)

        self._address = address

        self._output = ports.AudioOutputPort('out')
        self.add_output(self._output)

        self._pipe_in = None
        self._pipe_out = None
        self._buffer = bytearray()

    async def setup(self):
        await super().setup()
        logger.info("setup(): thread_id=%s", threading.get_ident())

        logger.info("Connecting to %s...", self._address)
        self._pipe_in = os.open(
            self._address + '.recv', os.O_RDONLY | os.O_NONBLOCK)
        os.set_blocking(self._pipe_in, True)

        self._pipe_out = os.open(
            self._address + '.send', os.O_RDWR | os.O_NONBLOCK)
        os.set_blocking(self._pipe_out, True)

    async def cleanup(self):
        if self._pipe_in is not None:
            os.close(self._pipe_in)
            self._pipe_in = None

        if self._pipe_out is not None:
            os.close(self._pipe_out)
            self._pipe_out = None

        self._buffer.clear()

        await super().cleanup()

    def _get_line(self):
        while True:
            eol = self._buffer.find(b'\n')
            if eol >= 0:
                line = self._buffer[:eol]
                del self._buffer[:eol+1]
                return line
            dat = os.read(self._pipe_in, 1024)
            #logger.debug("dat=%s", dat)
            self._buffer.extend(dat)

    def _get_bytes(self, num_bytes):
        while len(self._buffer) < num_bytes:
            dat = os.read(self._pipe_in, 1024)
            #logger.debug("dat=%s", dat)
            self._buffer.extend(dat)

        d = self._buffer[:num_bytes]
        del self._buffer[:num_bytes]
        return d

    def run(self, timepos):
        request = bytearray()
        request.extend(b'#FR=%d\n' % timepos)

        e = []
        if random.random() < 0.10:
            e.append(('foo', events.NoteOnEvent(
                timepos,
                music.Pitch.from_midi(random.randint(40, 90)))))

        for queue, event in e:
            request.extend(b'EVENT=%s\n' % queue.encode('utf-8'))
            serialized = pickle.dumps(event)
            request.extend(b'LEN=%d\n' % len(serialized))
            request.extend(serialized)

        request.extend(b'#END\n')

        while request:
            written = os.write(self._pipe_out, request)
            del request[:written]

        l = self._get_line()
        assert l == b'#FR=%d' % timepos, l

        l = self._get_line()
        assert l.startswith(b'SAMPLES=')
        num_samples = int(l[8:])

        l = self._get_line()
        assert l.startswith(b'LEN=')
        num_bytes = int(l[4:])

        samples = self._get_bytes(num_bytes)
        assert len(samples) == num_bytes

        self._output.frame.resize(0)
        self._output.frame.append_samples(samples, num_samples)
        assert len(self._output.frame) <= 4096
        self._output.frame.resize(4096)
