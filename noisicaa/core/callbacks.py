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
from typing import Any, Dict, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)


K = TypeVar('K')
T = TypeVar('T')
CallbackFunc = Callable[[T], None]


class Listener(Generic[T]):
    """Opaque container for a callback."""

    def __init__(self, registry: 'Callback[T]', callback: CallbackFunc) -> None:
        self.__registry = registry
        self.id = random.getrandbits(64)
        self.callback = callback

    def remove(self) -> None:
        self.__registry.remove(self)


class Callback(Generic[T]):
    def __init__(self) -> None:
        self.__lock = threading.RLock()
        self.__listeners = collections.OrderedDict()  # type: Dict[int, Listener]

    def clear(self) -> None:
        with self.__lock:
            self.__listeners.clear()

    def add(self, callback: CallbackFunc) -> Listener[T]:
        """Register a new callback.

        Args:
          callback: A callable with will be called.

        Returns:
          A listener, which should be used to unregister this callback.
        """

        if not callable(callback):
            raise TypeError(type(callback))

        listener = Listener(self, callback)
        with self.__lock:
            self.__listeners[listener.id] = listener

        return listener

    def add_listener(self, listener: Listener[T]) -> None:
        with self.__lock:
            self.__listeners[listener.id] = listener

    def remove(self, listener: Listener[T]) -> None:
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

    def call(self, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self.__lock:
            for listener in self.__listeners.values():
                listener.callback(*args, **kwargs)  # type: ignore

    async def async_call(self, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self.__lock:
            for listener in self.__listeners.values():
                await listener.callback(*args, **kwargs)  # type: ignore


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
