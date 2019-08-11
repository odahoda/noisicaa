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

import collections
import logging
import random
import threading
from typing import Any, Dict, List, Iterable, Callable, Awaitable, Generic, TypeVar

logger = logging.getLogger(__name__)


K = TypeVar('K')
T = TypeVar('T')
CB = TypeVar('CB')
L = TypeVar('L', bound='BaseListener')
R = TypeVar('R', bound='BaseCallback')
CallbackFunc = Callable[[T], None]
AsyncCallbackFunc = Callable[[T], Awaitable]


class BaseListener(Generic[T, CB, R]):
    """Opaque container for a callback."""

    def __init__(self, registry: R, callback: CB) -> None:
        self.__registry = registry
        self.id = random.getrandbits(64)
        self.callback = callback

    def remove(self) -> None:
        self.__registry.remove(self)


class Listener(Generic[T], BaseListener[T, CallbackFunc, 'Callback']):
    pass


class AsyncListener(Generic[T], BaseListener[T, AsyncCallbackFunc, 'AsyncCallback']):
    pass


class BaseCallback(Generic[T, CB, L]):
    def __init__(self) -> None:
        self.__lock = threading.RLock()
        self.__listeners = collections.OrderedDict()  # type: Dict[int, L]

    def clear(self) -> None:
        with self.__lock:
            self.__listeners.clear()

    def add(self, callback: CB) -> L:
        """Register a new callback.

        Args:
          callback: A callable with will be called.

        Returns:
          A listener, which should be used to unregister this callback.
        """

        listener = self._create_listener(callback)
        with self.__lock:
            self.__listeners[listener.id] = listener

        return listener

    def add_listener(self, listener: L) -> None:
        with self.__lock:
            self.__listeners[listener.id] = listener

    def remove(self, listener: L) -> None:
        """Remove a callback.

        Alternatively you can just call remove() on the listener returned by
        add_listener().

        Args:
          listener: The listener instance as returned by add_listener().

        Raises:
          KeyError: if the listener is not a valid callback.
        """

        with self.__lock:
            del self.__listeners[listener.id]

    def _create_listener(self, callback: CB) -> L:
        raise NotImplementedError

    def _call_sync(self, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self.__lock:
            for listener in self.__listeners.values():
                listener.callback(*args, **kwargs)

    async def _call_async(self, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self.__lock:
            for listener in self.__listeners.values():
                await listener.callback(*args, **kwargs)


class Callback(Generic[T], BaseCallback[T, CallbackFunc, Listener[T]]):
    def _create_listener(self, callback: CallbackFunc) -> Listener[T]:
        return Listener[T](self, callback)

    def call(self, *args: Any, **kwargs: Any) -> None:
        self._call_sync(*args, **kwargs)


class AsyncCallback(Generic[T], BaseCallback[T, AsyncCallbackFunc, AsyncListener[T]]):
    def _create_listener(self, callback: AsyncCallbackFunc) -> AsyncListener[T]:
        return AsyncListener[T](self, callback)

    async def call(self, *args: Any, **kwargs: Any) -> None:
        await self._call_async(*args, **kwargs)


class CallbackMap(Generic[K, T]):
    def __init__(self) -> None:
        self.__callbacks = {}  # type: Dict[K, Callback[T]]

    def add(self, key: K, func: CallbackFunc) -> Listener[T]:
        try:
            callback = self.__callbacks[key]
        except KeyError:
            callback = Callback[T]()
            self.__callbacks[key] = callback
        return callback.add(func)

    def call(self, key: K, *args: Any, **kwargs: Any) -> None:
        try:
            callback = self.__callbacks[key]
        except KeyError:
            return

        callback.call(*args, **kwargs)


class ListenerMap(Generic[K]):
    def __init__(self) -> None:
        self.__listeners = {}  # type: Dict[K, BaseListener]

    def cleanup(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

    def __getitem__(self, key: K) -> BaseListener:
        return self.__listeners[key]

    def __setitem__(self, key: K, listener: BaseListener) -> None:
        assert key not in self.__listeners
        self.__listeners[key] = listener

    def __delitem__(self, key: K) -> None:
        listener = self.__listeners.pop(key)
        listener.remove()


class ListenerList(object):
    def __init__(self) -> None:
        self.__listeners = []  # type: List[BaseListener]

    def cleanup(self) -> None:
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    def add(self, listener: BaseListener) -> None:
        self.__listeners.append(listener)

    def extend(self, listeners: Iterable[BaseListener]) -> None:
        self.__listeners.extend(listeners)
