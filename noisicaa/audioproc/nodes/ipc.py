#!/usr/bin/python3

import asyncio
import logging
import threading

from noisicaa.core import ipc

from .. import ports
from .. import node
from .. import frame
from .. import node_types

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

        self._stub = None

    async def setup(self):
        await super().setup()
        logger.info("setup(): thread_id=%s", threading.get_ident())

        logger.info("Connecting to %s...", self._address)
        self._stub = ipc.Stub(self.event_loop, self._address)
        await self._stub.connect()

    async def cleanup(self):
        if self._stub is not None:
            logger.info("Disconnecting from %s...", self._address)
            await self._stub.close()
        await super().cleanup()

    def run(self, timepos):
        self._output.frame.clear()

        logger.info("run(): thread_id=%s", threading.get_ident())

        future = asyncio.run_coroutine_threadsafe(
            self._stub.call('PROCESS_FRAME'), self.event_loop)
        event = threading.Event()
        future.add_done_callback(event.set)
        event.wait()
        logger.info("process_frame done")
