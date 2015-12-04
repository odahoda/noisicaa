#!/usr/bin/python3

import logging

from .state import StateBase

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


class Command(StateBase):
    # TODO: Some way to declare valid attributes
    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)

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


class CommandTarget(object):
    def __init__(self):
        self.__sub_targets = {}
        self.__is_root = False

    def set_root(self):
        self.__is_root = True

    def add_sub_target(self, name, obj):
        self.__sub_targets[name] = obj

    def get_sub_target(self, name):
        try:
            return self.__sub_targets[name]
        except KeyError:
            raise CommandError("Target '%s' not found" % name)

    def get_object(self, address):
        if address.startswith('/'):
            assert self.__is_root
            address = address[1:]

        if address == '':
            return self

        parts = address.split('/', 1)
        assert len(parts) >= 1
        obj = self.get_sub_target(parts[0])
        return obj.get_object(parts[1] if len(parts) > 1 else '')


class CommandDispatcher(CommandTarget):
    def dispatch_command(self, target, cmd):
        obj = self.get_object(target)
        return cmd.run(obj)
