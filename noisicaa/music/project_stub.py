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


class ProjectStub(ipc.Stub):
    @property
    def project(self):
        return ObjectProxy(self, '/')
        
    async def shutdown(self):
        await self.call('SHUTDOWN')

    async def get_property(self, target, prop):
        result = await self.get_properties(target, [prop])
        return result[prop]

    async def get_properties(self, target, props):
        request = ipc.serialize([target, props])
        response = await self.call('GETPROPS', request)

        results = {}
        for prop, (vtype, value) in ipc.deserialize(response).items():
            if vtype == 'proxy':
                value = ObjectProxy(self, value)
            elif vtype == 'value':
                pass
            else:
                raise ValueError("Unexpected value type %s" % vtype)
            results[prop] = value

        return results
