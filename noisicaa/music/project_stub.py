#!/usr/bin/python3

import logging

from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class ObjectProxy(object):
    def __init__(self, project_stub, address):
        self._project_stub = project_stub
        self._address = address

    def __getattr__(self, attr):
        return self._project_stub.get_property(self._address, attr)


class ProjectStub(ipc.Stub):
    @property
    def project(self):
        return ObjectProxy(self, '/')
        
    def shutdown(self):
        self.call('SHUTDOWN')

    def get_property(self, target, prop):
        return self.get_properties(target, [prop])[prop]

    def get_properties(self, target, props):
        request = ipc.serialize([target, props])
        response = self.call('GETPROPS', request)

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
