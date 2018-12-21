#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import functools
import asyncio
import logging
import signal
from typing import Any, Optional, Sequence

from PyQt5 import QtWidgets
import quamash

from noisicaa import core
from noisicaa import runtime_settings as runtime_settings_lib
from . import editor_app

logger = logging.getLogger(__name__)


class UISubprocess(core.SubprocessMixin, core.ProcessBase):
    def __init__(
            self, *,
            runtime_settings: runtime_settings_lib.RuntimeSettings,
            paths: Sequence[str],
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.runtime_settings = runtime_settings
        self.paths = paths

        self._shutting_down = None  # type: asyncio.Event
        self.exit_code = None  # type: Optional[int]
        self.qt_app = None  # type: QtWidgets.QApplication
        self.app = None  # type: editor_app.EditorApp

    def create_event_loop(self) -> asyncio.AbstractEventLoop:
        self.qt_app = editor_app.QApplication()
        return quamash.QEventLoop(self.qt_app)

    async def setup(self) -> None:
        self._shutting_down = asyncio.Event(loop=self.event_loop)
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.event_loop.add_signal_handler(
                sig, functools.partial(self.handle_signal, sig))
        await super().setup()

        self.app = editor_app.EditorApp(
            qt_app=self.qt_app,
            process=self,
            runtime_settings=self.runtime_settings,
            paths=self.paths)
        await self.app.setup()

    async def cleanup(self) -> None:
        if self.app is not None:
            await self.app.cleanup()
            self.app = None

        await super().cleanup()

    async def run(self) -> int:
        await self._shutting_down.wait()
        return self.exit_code or 0

    def quit(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self._shutting_down.set()

    def handle_signal(self, sig: signal.Signals) -> None:
        logger.info("%s received.", sig.name)
        self.quit(0)
