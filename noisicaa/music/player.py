#!/usr/bin/python3

import functools
import asyncio
import logging
import os.path
import tempfile
import threading
import time
import uuid

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc

from . import project
from . import mutations
from . import commands

logger = logging.getLogger(__name__)


class AudioProcClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class AudioProcClient(
        audioproc.AudioProcClientMixin, AudioProcClientImpl):
    pass


class AudioStreamProxy(object):
    def __init__(self, address, socket_dir=None):
        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'player.%s.pipe' % uuid.uuid4().hex)

        self._server = audioproc.AudioStreamServer(self.address)
        self._client = audioproc.AudioStreamClient(address)

        self._thread = threading.Thread(target=self.main)

    def setup(self):
        self._server.setup()
        self._client.setup()
        self._thread.start()

    def cleanup(self):
        self._thread.join()
        self._client.cleanup()
        self._server.cleanup()

    def main(self):
        while True:
            try:
                request = self._server.receive_frame()
                self._client.send_frame(request)
                response = self._client.receive_frame()
                self._server.send_frame(response)
            except audioproc.StreamClosed:
                break


class Player(object):
    def __init__(self, sheet, manager, event_loop):
        self.sheet = sheet
        self.manager = manager
        self.event_loop = event_loop

        self.id = uuid.uuid4().hex
        self.server = ipc.Server(self.event_loop, 'player')

        self.setup_complete = False

        self.audioproc_address = None
        self.audioproc_client = None
        self.audiostream_address = None

        self.mutation_listener = None
        self.pending_pipeline_mutations = None

        self.proxy = None

    @property
    def proxy_address(self):
        assert self.proxy is not None
        return self.proxy.address

    async def setup(self):
        await self.server.setup()

        self.audioproc_address = await self.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'player')
        self.audioproc_client = AudioProcClient(
            self.event_loop, self.server)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(self.audioproc_address)
        self.audiostream_address = await self.audioproc_client.set_backend('ipc')

        self.proxy = AudioStreamProxy(self.audiostream_address)
        self.proxy.setup()

        self.pending_pipeline_mutations = []
        self.mutation_listener = self.sheet.listeners.add(
            'pipeline_mutations', self.handle_pipeline_mutation)

        self.sheet.add_to_pipeline()
        pipeline_mutations = self.pending_pipeline_mutations[:]
        self.pending_pipeline_mutations = None

        for mutation in pipeline_mutations:
            await self.publish_pipeline_mutation(mutation)

        await self.audioproc_client.dump()

    async def cleanup(self):
        if self.mutation_listener is not None:
            self.mutation_listener.remove()
            self.mutation_listener = None

        if self.proxy is not None:
            self.proxy.cleanup()
            self.proxy = None

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None
            self.audioproc_address = None
            self.audiostream_address = None

        await self.server.cleanup()

    def handle_pipeline_mutation(self, mutation):
        if self.pending_pipeline_mutations is not None:
            self.pending_pipeline_mutations.append(mutation)
        else:
            self.event_loop.create_task(
                self.publish_pipeline_mutation(mutation))

    async def publish_pipeline_mutation(self, mutation):
        if self.audioproc_client is None:
            return

        if isinstance(mutation, mutations.AddNode):
            await self.audioproc_client.add_node(
                mutation.node_type, id=mutation.node_id,
                name=mutation.node_name, **mutation.args)

        elif isinstance(mutation, mutations.RemoveNode):
            await self.audioproc_client.remove_node(mutation.node_id)

        elif isinstance(mutation, mutations.ConnectPorts):
            await self.audioproc_client.connect_ports(
                mutation.src_node, mutation.src_port,
                mutation.dest_node, mutation.dest_port)

        elif isinstance(mutation, mutations.DisconnectPorts):
            await self.audioproc_client.disconnect_ports(
                mutation.src_node, mutation.src_port,
                mutation.dest_node, mutation.dest_port)

        else:
            raise ValueError(type(mutation))
