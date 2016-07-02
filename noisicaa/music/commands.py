#!/usr/bin/python3

import logging

from .state import StateBase

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


class Command(StateBase):
    def __init__(self, state=None):
        super().__init__(state)

    def __str__(self):
        return '%s{%s}' % (
            type(self).__name__,
            ', '.join('%s=%r' % (k, v) for k, v in sorted(self.state.items())))
    __repr__ = __str__

    def __eq__(self, other):
        if self.__class__ is not other.__class__:
            return False
        for prop_name in self.list_property_names():
            if prop_name == 'id':
                continue
            if getattr(self, prop_name) != getattr(other, prop_name):
                return False
        return True
