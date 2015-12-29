#!/usr/bin/python3

import logging
import uuid
import threading

logger = logging.getLogger(__name__)


class Listener(object):
    """Only internally used by CallbackRegistry."""

    def __init__(self, target, callback):
        self.id = str(uuid.uuid4())
        self.target = target
        self.callback = callback


class CallbackRegistry(object):
    """A registry for callbacks.

    Clients can register callbacks for certain targets that they are interested
    in.

    Targets are identified by arbitrary identifiers, which can be any object,
    which is suitable as a dictionary key. How targets look like is defined
    by the owner of the registry.

    The arguments with which the callbacks are called is also defined by the
    owner of the registry.
    """

    def __init__(self):
        self._listeners = {}
        self._target_map = {}
        self._lock = threading.Lock()

    def add(self, target, callback):
        """Register a new callback.

        Args:
          target: The target identifier for which you want to receive callbacks.
          callback: A callable with will be called.

        Returns:
          A listener ID, which should be used to unregister this callback.
        """

        listener = Listener(target, callback)
        with self._lock:
            self._listeners[listener.id] = listener
            self._target_map.setdefault(target, []).append(listener.id)
        logger.info("Added listener %s to target %s", listener.id, target)
        return listener.id

    def remove(self, listener_id):
        """Remove a callback.

        Args:
          listener_id: The ID as returned by add_listener().

        Raises:
          KeyError: if the listener_id is not a valid callback.
        """

        with self._lock:
            listener = self._listeners[listener_id]
            del self._listeners[listener.id]
            self._target_map[listener.target].remove(listener.id)
        logger.info(
            "Removed listener %s from target %s", listener.id, listener.target)

    def call(self, target, *args, **kwargs):
        """Call all callbacks registered for a given target.

        This method should only be called by the owner of the registry.

        Args:
          target: The target identifier for which the callbacks should be called.
          args, kwargs: The arguments passed to all callbacks.
        """

        with self._lock:
            for listener_id in self._target_map.get(target, []):
                listener = self._listeners[listener_id]
                listener.callback(*args, **kwargs)
