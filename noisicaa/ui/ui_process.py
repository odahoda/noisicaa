#!/usr/bin/python3

import functools
import asyncio
import logging
import threading
import time
import uuid

import quamash
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from noisicaa import core
from noisicaa.core import ipc

from . import editor_app
from .. import runtime_settings

logger = logging.getLogger(__name__)


class UIProcessMixin(object):
    def __init__(self, runtime_settings, paths, **kwargs):
        super().__init__(**kwargs)

        self.app = self.create_app(self, runtime_settings, paths)

    def create_app(self, *args, **kwargs):
        return editor_app.EditorApp(*args, **kwargs)

    def create_event_loop(self):
        return quamash.QEventLoop(self.app)

    async def setup(self):
        self._shutting_down = asyncio.Event()

        await super().setup()
        await self.app.setup()

    async def cleanup(self):
        await self.app.cleanup()
        await super().cleanup()

    async def run(self):
        await self._shutting_down.wait()
        return self.exit_code

    def quit(self, exit_code=0):
        self.exit_code = exit_code
        self._shutting_down.set()


class UIProcess(UIProcessMixin, core.ProcessImpl):
    pass
