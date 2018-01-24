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

import quamash

from noisicaa import core

from . import editor_app

logger = logging.getLogger(__name__)


class UISubprocess(core.SubprocessMixin, core.ProcessBase):
    def __init__(self, *, runtime_settings, paths, **kwargs):
        super().__init__(**kwargs)

        self._shutting_down = None
        self.exit_code = None

        self.app = self.create_app(
            process=self,
            runtime_settings=runtime_settings,
            paths=paths)

    def create_app(self, **kwargs):
        return editor_app.EditorApp(**kwargs)

    def create_event_loop(self):
        return quamash.QEventLoop(self.app)

    async def setup(self):
        self._shutting_down = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.event_loop.add_signal_handler(
                sig, functools.partial(self.handle_signal, sig))
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

    def handle_signal(self, sig):
        logger.info("%s received.", sig.name)
        self.quit(0)
