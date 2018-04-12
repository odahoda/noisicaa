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

import logging
import uuid
import threading
from typing import Any, Dict, Callable, List, Optional  # pylint: disable=unused-import

logger = logging.getLogger(__name__)


Callback = Callable[..., None]
RegisterCallback = Callable[[str, str, bool], None]


class Listener(object):
    """Only internally used by CallbackRegistry."""

    def __init__(self, registry: 'CallbackRegistry', target: str, callback: Callback) -> None:
        self.__registry = registry
        self.id = str(uuid.uuid4())
        self.target = target
        self.callback = callback

    def remove(self) -> None:
        self.__registry.remove(self)


class CallbackRegistry(object):
    """A registry for callbacks.

    Clients can register callbacks for certain targets that they are interested
    in.

    Targets are identified by arbitrary identifiers, which can be any object,
    which is suitable as a dictionary key. How targets look like is defined
    by the owner of the registry.

    The arguments with which the callbacks are called is also defined by the
    owner of the registry.

    This class is thread-safe.
    """

    def __init__(self, register_cb: Optional[RegisterCallback] = None) -> None:
        """Create a new registry.

        Args:
          register_cb: Optional callable, which will be called before a listener
              is added or after it was removed. It will be called with arguments
              (target, listener_id, add_or_remove). add_or_remove is True, when
              the listener has been added or False when removed.
        """

        self.__register_cb = register_cb
        self.__listeners = {}  # type: Dict[str, Listener]
        self.__target_map = {}  # type: Dict[str, List[str]]
        self.__lock = threading.RLock()

    def clear(self) -> None:
        with self.__lock:
            self.__listeners.clear()
            self.__target_map.clear()

    def add(self, target: str, callback: Callback) -> Listener:
        """Register a new callback.

        Args:
          target: The target identifier for which you want to receive callbacks.
          callback: A callable with will be called.

        Returns:
          A listener, which should be used to unregister this callback.
        """

        listener = Listener(self, target, callback)
        if self.__register_cb is not None:
            self.__register_cb(target, listener.id, True)
        with self.__lock:
            self.__listeners[listener.id] = listener
            self.__target_map.setdefault(target, []).append(listener.id)
        logger.debug("Added listener %s to target %s", listener.id, target)
        return listener

    def remove(self, listener: Listener) -> None:
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
            self.__target_map[listener.target].remove(listener.id)
        if self.__register_cb is not None:
            self.__register_cb(listener.target, listener.id, False)
        logger.debug(
            "Removed listener %s from target %s", listener.id, listener.target)

    def call(self, target: str, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self.__lock:
            for listener_id in self.__target_map.get(target, []):
                listener = self.__listeners[listener_id]
                listener.callback(*args, **kwargs)
