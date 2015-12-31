#!/usr/bin/python3

import logging
import uuid
import threading

logger = logging.getLogger(__name__)


class Listener(object):
    """Only internally used by CallbackRegistry."""

    def __init__(self, registry, target, callback):
        self._registry = registry
        self.id = str(uuid.uuid4())
        self.target = target
        self.callback = callback

    def remove(self):
        self._registry.remove(self)


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

    def __init__(self, register_cb=None):
        """Create a new registry.

        Args:
          register_cb: Optional callable, which will be called before a listener
              is added or after it was removed. It will be called with arguments
              (target, listener_id, add_or_remove). add_or_remove is True, when
              the listener has been added or False when removed.
        """

        self._register_cb = register_cb
        self._listeners = {}
        self._target_map = {}
        self._lock = threading.Lock()

    def add(self, target, callback):
        """Register a new callback.

        Args:
          target: The target identifier for which you want to receive callbacks.
          callback: A callable with will be called.

        Returns:
          A listener, which should be used to unregister this callback.
        """

        listener = Listener(self, target, callback)
        if self._register_cb is not None:
            self._register_cb(target, listener.id, True)
        with self._lock:
            self._listeners[listener.id] = listener
            self._target_map.setdefault(target, []).append(listener.id)
        logger.info("Added listener %s to target %s", listener.id, target)
        return listener

    def remove(self, listener):
        """Remove a callback.

        Alternatively you can just call remove() on the listener returned by
        add_listener().

        Args:
          listener: The listener instance as returned by add_listener().

        Raises:
          KeyError: if the listener is not a valid callback.
        """

        with self._lock:
            del self._listeners[listener.id]
            self._target_map[listener.target].remove(listener.id)
        if self._register_cb is not None:
            self._register_cb(listener.target, listener.id, False)
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
