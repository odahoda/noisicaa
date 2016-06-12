#!/usr/bin/python3

import logging

from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class ObjectProxy(object):
    def __init__(self, project_stub, address):
        self._project_stub = project_stub
        self._address = address

    def __getattr__(self, attr):
        return self._project_stub._event_loop.run_until_complete(
            self._project_stub.get_property(self._address, attr))


class ListenerProxy(object):
    def __init__(self, stub, listener_id, callback):
        self._stub = stub
        self.listener_id = listener_id
        self.callback = callback

    async def remove(self):
        await self._stub.remove_listener(self.listener_id)


class ProjectStub(ipc.Stub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_id = None
        self._listeners = {}

    @property
    def project(self):
        return ObjectProxy(self, '/')

    def listener_callback(self, listener_id, args):
        try:
            listener = self._listeners[listener_id]
        except KeyError:
            logger.error("Callback for unknown listener %s", listener_id)
        else:
            listener.callback(*args)

    async def shutdown(self):
        await self.call('SHUTDOWN')

    async def start_session(self, callback_server):
        self._session_id = await self.call('START_SESSION', callback_server)
        return self._session_id

    async def get_property(self, target, prop):
        result = await self.get_properties(target, [prop])
        return result[prop]

    async def get_properties(self, target, props):
        response = await self.call('GETPROPS', self._session_id, target, props)

        results = {}
        for prop, (vtype, value) in response.items():
            if vtype == 'proxy':
                value = ObjectProxy(self, value)
            elif vtype == 'value':
                pass
            else:
                raise ValueError("Unexpected value type %s" % vtype)
            results[prop] = value

        return results

    async def add_listener(self, target, prop, callback):
        listener_id = await self.call(
            'ADD_LISTENER', self._session_id, target, prop)
        proxy = ListenerProxy(self, listener_id, callback)
        self._listeners[listener_id] = proxy
        return proxy

    async def remove_listener(self, listener_id):
        proxy = self._listeners[listener_id]
        await self.call('REMOVE_LISTENER', self._session_id, listener_id)
        del self._listeners[listener_id]

    async def test(self):
        await self.call('TEST')
