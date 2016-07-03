#!/usr/bin/python3

import logging
import uuid

from .exceptions import Error
from .ports import OutputPort, InputPort

logger = logging.getLogger(__name__)


class Node(object):
    desc = None

    def __init__(self, event_loop, name=None, id=None):
        self.event_loop = event_loop
        self.id = id or uuid.uuid4().hex
        self.pipeline = None
        self._name = name or type(self).__name__
        self.inputs = {}
        self.outputs = {}

    @property
    def name(self):
        return self._name

    def send_notification(self, notification):
        self.pipeline.add_notification(self.id, notification)

    def add_input(self, port):
        if not isinstance(port, InputPort):
            raise Error("Must be InputPort")
        port.owner = self
        self.inputs[port.name] = port

    def add_output(self, port):
        if not isinstance(port, OutputPort):
            raise Error("Must be OutputPort")
        port.owner = self
        self.outputs[port.name] = port

    @property
    def parent_nodes(self):
        parents = []
        for port in self.inputs.values():
            for upstream_port in port.inputs:
                parents.append(upstream_port.owner)
        return parents

    async def setup(self):
        """Set up the node.

        Any expensive initialization should go here.
        """
        logger.info("%s: setup()", self.name)

    async def cleanup(self):
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def collect_inputs(self):
        for port in self.inputs.values():
            port.collect_inputs()

    def run(self, timepos):
        raise NotImplementedError
