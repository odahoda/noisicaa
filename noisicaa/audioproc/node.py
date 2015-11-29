#!/usr/bin/python3

import logging

from .exceptions import Error
from .ports import OutputPort, InputPort

logger = logging.getLogger(__name__)


class Node(object):
    def __init__(self, name=None):
        self.pipeline = None
        self._name = name or type(self).__name__
        self.inputs = {}
        self.outputs = {}
        self._started = False

    @property
    def name(self):
        return self._name

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
        return [port.input.owner
                for port in self.inputs.values()
                if port.is_connected]

    @property
    def started(self):
        return self._started

    def setup(self):
        """Set up the node.

        Any expensive initialization should go here.
        """
        logger.info("%s: setup()", self.name)

    def cleanup(self):
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def start(self):
        """Start the node."""
        logger.info("%s: start()", self.name)
        self._started = True
        for port in self.inputs.values():
            port.start()

    def stop(self):
        """Stop the node."""
        logger.info("%s: stop()", self.name)
        for port in self.inputs.values():
            port.stop()
        self._started = False

    def run(self):
        raise NotImplementedError
