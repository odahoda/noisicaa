#!/usr/bin/python3

import logging

from noisicaa import core
from .state import StateBase

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


class Command(StateBase):
    mutations = core.ListProperty(list)

    command_classes = {}

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

    @classmethod
    def register_command(cls, cmd_cls):
        assert cmd_cls.__name__ not in cls.command_classes
        cls.command_classes[cmd_cls.__name__] = cmd_cls

    @classmethod
    def create(cls, command_name, **kwargs):
        cmd_cls = cls.command_classes[command_name]
        return cmd_cls(**kwargs)

    @classmethod
    def create_from_state(cls, state):
        cls_name = state['__class__']
        c = cls.command_classes[cls_name]
        return c(state=state)
