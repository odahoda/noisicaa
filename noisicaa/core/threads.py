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

import asyncio
import concurrent.futures
import logging
import threading
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)


class Thread(threading.Thread):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            target: Callable[[], Any],
            done_cb: Awaitable = None):
        super().__init__(target=self.__main)

        self.__event_loop = event_loop
        self.__target = target
        self.__done_cb = done_cb

        self.__thread_done = concurrent.futures.Future()

    def start(self):
        super().start()
        logger.info("Started thread %08x", self.ident)

    async def join(self, timeout=None) -> None:
        done_fut = asyncio.wrap_future(self.__thread_done, loop=self.__event_loop)
        await asyncio.wait_for(asyncio.shield(done_fut), timeout, loop=self.__event_loop)
        assert self.__thread_done.done()

        super().join()

        return done_fut.result()

    def __main(self) -> None:
        try:
            result = self.__target()
        except Exception as exc:  # pylint: disable=broad-except
            logger.info(
                "Thread %08x finished with an exception: %s: %s",
                self.ident, type(exc).__name__, exc)
            self.__thread_done.set_exception(exc)
        else:
            logger.info("Thread %08x finished successfully", self.ident)
            self.__thread_done.set_result(result)
        finally:
            if self.__done_cb is not None:
                asyncio.run_coroutine_threadsafe(self.__done_cb, self.__event_loop)
