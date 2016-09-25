#!/usr/bin/python3

import contextlib
import logging

from noisicaa import core
from . import state

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


class CommandLog(state.StateBase):
    ops = core.ListProperty(object)
    slots = core.ListProperty(object)

    def __init__(self, state=None):
        super().__init__(state=state)

    def __str__(self):
        return '<CommandLog %s>' % ' '.join(name for name, _ in self.ops)
    __repr__ = __str__

    def add_slot(self, value):
        if isinstance(value, state.StateBase):
            value = ('object', value.serialize())
        else:
            value = ('basic', value)
        self.slots.append(value)
        return len(self.slots) - 1

    def get_slot(self, cls_map, slot_id):
        vtype, value = self.slots[slot_id]
        if vtype == 'object':
            cls_name = value['__class__']
            cls = cls_map[cls_name]
            value = cls(state=value)
        else:
            assert vtype == 'basic'
        return value

    def add_operation(self, name, *args):
        self.ops.append([name, args])


def _assert_equal(a, b):
    if isinstance(a, state.StateBase):
        a = 'obj:' + a.id
    if isinstance(b, state.StateBase):
        b = 'obj:' + b.id
    assert a == b, '%r != %r' % (a, b)


class Command(state.RootMixin, state.StateBase):
    log = core.ObjectProperty(CommandLog)
    status = core.Property(str)

    command_classes = {}

    def __init__(self, state=None):
        self.__in_mutator = False

        super().__init__(state)
        if state is None:
            self.status = 'NOT_APPLIED'
            self.log = CommandLog()

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

    @contextlib.contextmanager
    def __custom_mutator(self):
        assert not self.__in_mutator
        self.__in_mutator = True
        try:
            yield
        finally:
            self.__in_mutator = False

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

    @property
    def is_noop(self):
        return len(self.log.ops) == 0

    def set_property(self, obj, prop_name, new_value):
        old_value = getattr(obj, prop_name)
        with self.__custom_mutator():
            setattr(obj, prop_name, new_value)

        old_slot_id = self.log.add_slot(old_value)
        new_slot_id = self.log.add_slot(new_value)
        self.log.add_operation(
            'SET_PROPERTY', obj.id, prop_name, old_slot_id, new_slot_id)

    def list_insert(self, obj, prop_name, index, new_value):
        lst = getattr(obj, prop_name)
        with self.__custom_mutator():
            lst.insert(index, new_value)

        slot_id = self.log.add_slot(new_value)
        self.log.add_operation(
            'LIST_INSERT', obj.id, prop_name, index, slot_id)

    def list_delete(self, obj, prop_name, index):
        lst = getattr(obj, prop_name)
        old_value = lst[index]
        with self.__custom_mutator():
            del lst[index]

        slot_id = self.log.add_slot(old_value)
        self.log.add_operation(
            'LIST_DELETE', obj.id, prop_name, index, slot_id)

    def list_move(self, obj, prop_name, old_index, new_index):
        if new_index > old_index:
            new_index -= 1

        lst = getattr(obj, prop_name)
        value = lst[old_index]
        with self.__custom_mutator():
            del lst[old_index]
            lst.insert(new_index, value)

        slot_id = self.log.add_slot(value)
        self.log.add_operation(
            'LIST_DELETE', obj.id, prop_name, old_index, slot_id)
        self.log.add_operation(
            'LIST_INSERT', obj.id, prop_name, new_index, slot_id)

    def _handle_model_change(self, obj, change):
        if self.__in_mutator:
            return

        if isinstance(change, core.PropertyValueChange):
            if isinstance(
                    obj.get_property(change.prop_name),
                    core.ObjectReferenceProperty):
                old_value = (
                    change.old_value.id
                    if change.old_value is not None
                    else None)
                new_value = (
                    change.old_value.id
                    if change.old_value is not None
                    else None)

            else:
                old_value = change.old_value
                new_value = change.new_value

            old_slot_id = self.log.add_slot(old_value)
            new_slot_id = self.log.add_slot(new_value)

            self.log.add_operation(
                'SET_PROPERTY', obj.id, change.prop_name,
                old_slot_id, new_slot_id)

        elif isinstance(change, core.PropertyListInsert):
            lst = getattr(obj, change.prop_name)
            slot_id = self.log.add_slot(change.new_value)
            self.log.add_operation(
                'LIST_INSERT', obj.id, change.prop_name,
                change.index, slot_id)

        elif isinstance(change, core.PropertyListDelete):
            lst = getattr(obj, change.prop_name)
            slot_id = self.log.add_slot(change.old_value)
            self.log.add_operation(
                'LIST_DELETE', obj.id, change.prop_name, change.index,
                slot_id)

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def run(self, obj):
        raise NotImplementedError

    def apply(self, obj):
        assert self.status == 'NOT_APPLIED'

        listener = obj.root.listeners.add(
            'model_changes', self._handle_model_change)
        try:
            result = self.run(obj)
        except:
            self.status = 'FAILED'
            raise
        finally:
            listener.remove()

        self.status = 'APPLIED'
        return result

    def redo(self, obj):
        assert self.status == 'APPLIED'
        root = obj.root

        for op, args in self.log.ops:
            if op == 'SET_PROPERTY':
                obj_id, prop_name, old_slot_id, new_slot_id = args
                obj = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                _assert_equal(getattr(obj, prop_name), old_value)
                setattr(obj, prop_name, new_value)

            elif op == 'LIST_INSERT':
                obj_id, prop_name, index, new_slot_id = args
                obj = root.get_object(obj_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                lst = getattr(obj, prop_name)
                lst.insert(index, new_value)

            elif op == 'LIST_DELETE':
                obj_id, prop_name, index, old_slot_id = args
                obj = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)

                lst = getattr(obj, prop_name)
                _assert_equal(lst[index], old_value)
                del lst[index]

            else:
                raise ValueError("Unknown op %s" % op)

    def undo(self, obj):
        assert self.status == 'APPLIED'
        root = obj.root

        for op, args in reversed(self.log.ops):
            if op == 'SET_PROPERTY':
                obj_id, prop_name, old_slot_id, new_slot_id = args
                obj = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                current_value = getattr(obj, prop_name)
                _assert_equal(current_value, new_value)
                setattr(obj, prop_name, old_value)

            elif op == 'LIST_INSERT':
                obj_id, prop_name, index, new_slot_id = args
                obj = root.get_object(obj_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                lst = getattr(obj, prop_name)
                _assert_equal(lst[index], new_value)
                del lst[index]

            elif op == 'LIST_DELETE':
                obj_id, prop_name, index, old_slot_id = args
                obj = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)

                lst = getattr(obj, prop_name)
                lst.insert(index, old_value)

            else:
                raise ValueError("Unknown op %s" % op)


Command.register_class(CommandLog)
