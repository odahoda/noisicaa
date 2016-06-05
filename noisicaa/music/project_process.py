#!/usr/bin/python3

import logging
import threading
import time

from noisicaa import core
from noisicaa.core import ipc

from . import project

logger = logging.getLogger(__name__)


class ProjectProcess(core.ProcessImpl):
    def setup(self):
        self._shutting_down = threading.Event()
        self.server.add_command_handler('GETPROPS', self.handle_getprops)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.project = project.Project()

    def run(self):
        self._shutting_down.wait()

    def handle_getprops(self, payload):
        address, properties = ipc.deserialize(payload)
        obj = self.project.get_object(address)

        response = {}
        for prop in properties:
            value = getattr(obj, prop)
            if isinstance(value, core.StateBase):
                response[prop] = ['proxy', value.address]
            else:
                response[prop] = ['value', value]

        return ipc.serialize(response)

    def handle_shutdown(self, payload):
        self._shutting_down.set()
