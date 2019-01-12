#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
import enum
import logging
from typing import Callable, Optional

from . import callbacks

logger = logging.getLogger(__name__)


class BackendState(enum.Enum):
    Stopped = 'stopped'
    Starting = 'starting'
    Running = 'running'
    Crashed = 'crashed'
    Stopping = 'stopping'


class ManagedBackend(object):  # pragma: no coverage
    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def started(self, mgr: 'BackendManager') -> None:
        pass

    async def stopped(self, mgr: 'BackendManager') -> None:
        pass


class BackendManager(object):
    def __init__(self, event_loop: asyncio.AbstractEventLoop, backend: ManagedBackend) -> None:
        self.__event_loop = event_loop
        self.__backend = backend

        self.__state = BackendState.Stopped
        self.__state_changed = asyncio.Event(loop=self.__event_loop)
        self.__state_listeners = callbacks.Callback[BackendState]()
        self.__start_backend_result = None  # type: asyncio.Future
        self.__stop_lock = asyncio.Lock(loop=self.__event_loop)
        self.__stop_backend_result = None  # type: asyncio.Future

    @property
    def is_running(self) -> bool:
        return self.__state == BackendState.Running

    def add_state_listener(self, callback: Callable[[BackendState], None]) -> callbacks.Listener:
        return self.__state_listeners.add(callback)

    async def wait_until_running(self, *, timeout: Optional[float] = None) -> None:
        assert self.__start_backend_result is not None
        await asyncio.wait_for(self.__start_backend_result, timeout, loop=self.__event_loop)
        self.__start_backend_result.result()
        self.__start_backend_result = None

    async def wait_until_stopped(self, *, timeout: Optional[float] = None) -> None:
        assert self.__stop_backend_result is not None
        await asyncio.wait_for(self.__stop_backend_result, timeout, loop=self.__event_loop)
        self.__stop_backend_result.result()
        self.__stop_backend_result = None

    def start(self) -> None:
        if self.__state == BackendState.Stopped:
            self.__set_state(BackendState.Starting)

            assert self.__start_backend_result is None
            self.__start_backend_result = asyncio.Future(loop=self.__event_loop)
            self.__event_loop.create_task(self.__start_backend())

        else:  # pragma: no coverage
            raise AssertionError("Unexpected state %s" % self.__state.value)

    def stop(self) -> None:
        if self.__state in (BackendState.Stopped, BackendState.Stopping):
            pass

        elif self.__state in (BackendState.Running, BackendState.Crashed):
            self.__set_state(BackendState.Stopping)

            assert self.__stop_backend_result is None
            self.__stop_backend_result = asyncio.Future(loop=self.__event_loop)
            self.__event_loop.create_task(self.__stop_backend())

        else:  # pragma: no coverage
            raise AssertionError("Unexpected state %s" % self.__state.value)

    def crashed(self) -> None:
        if self.__state in (BackendState.Crashed, BackendState.Stopping, BackendState.Stopped):
            pass

        elif self.__state == BackendState.Running:
            self.__set_state(BackendState.Crashed)

            task = self.__event_loop.create_task(self.__stop_backend())
            task.add_done_callback(lambda task: task.result())

        else:  # pragma: no coverage
            raise AssertionError("Unexpected state %s" % self.__state.value)

    def __set_state(self, new_state: BackendState) -> None:
        logger.info("State %s -> %s", self.__state.value, new_state.value)
        assert new_state != self.__state
        self.__state = new_state
        self.__state_changed.set()
        self.__state_listeners.call(new_state)

    async def __start_backend(self) -> None:
        try:
            await self.__backend.start()

        except Exception as exc:  # pylint: disable=broad-except
            self.__set_state(BackendState.Crashed)
            self.__start_backend_result.set_exception(exc)
            await self.__backend.stop()

        else:
            self.__set_state(BackendState.Running)
            self.__start_backend_result.set_result(None)

            await self.__backend.started(self)

    async def __stop_backend(self) -> None:
        async with self.__stop_lock:
            if self.__state == BackendState.Stopped:
                return

            try:
                await self.__backend.stop()

            except Exception as exc:  # pylint: disable=broad-except
                if self.__stop_backend_result is not None:
                    self.__stop_backend_result.set_exception(exc)
                    return
                else:
                    raise

            else:
                if self.__stop_backend_result is not None:
                    self.__stop_backend_result.set_result(None)

            finally:
                self.__set_state(BackendState.Stopped)
                await self.__backend.stopped(self)
