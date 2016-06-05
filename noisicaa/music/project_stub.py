#!/usr/bin/python3

import logging

from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class ProjectStub(ipc.Stub):
    def shutdown(self):
        self.call('SHUTDOWN')

    def get_property(self, target, prop):
        return self.get_properties(target, [prop])[prop]

    def get_properties(self, target, props):
        request = ipc.serialize([target, props])
        response = self.call('GETPROPS', request)
        return ipc.deserialize(response)
