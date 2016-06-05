#!/usr/bin/python3

import logging
import threading
import time

from noisicaa import core
from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class ProjectProcess(core.ProcessImpl):
    def setup(self):
        self._shutting_down = threading.Event()
        self.server.add_command_handler('HELLO', self.handle_hello)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)

    def run(self):
        self._shutting_down.wait()

    def handle_hello(self, payload):
        print(payload)

    def handle_shutdown(self, payload):
        self._shutting_down.set()
