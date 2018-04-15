#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import contextlib
import logging
from typing import (  # pylint: disable=unused-import
    cast, Any, Optional, Generator, Dict, List, Tuple, Type
)

from noisicaa import core
from . import state as state_lib

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


Op = Tuple[str, List[Any]]
Ops = List[Op]
Slot = Tuple[str, Any]
Slots = List[Slot]

class CommandLog(state_lib.StateBase):
    ops = core.ListProperty(object)
    slots = core.ListProperty(object)

    def __str__(self) -> str:
        return '<CommandLog %s>' % ' '.join(name for name, _ in cast(Ops, self.ops))
    __repr__ = __str__

    def add_slot(self, value: Any) -> int:
        if isinstance(value, state_lib.StateBase):
            value = ('object', value.serialize())
        else:
            value = ('basic', value)
        self.slots.append(value)
        return len(self.slots) - 1

    def get_slot(self, cls_map: Dict[str, Type[state_lib.StateBase]], slot_id: int) -> Any:
        vtype, value = cast(Slot, self.slots[slot_id])
        if vtype == 'object':
            cls_name = value['__class__']
            cls = cls_map[cls_name]
            value = cls(state=value)
        else:
            assert vtype == 'basic'
        return value

    def add_operation(self, name: str, *args: Any) -> None:
        self.ops.append([name, args])


def _assert_equal(a: Any, b: Any) -> None:
    if isinstance(a, state_lib.StateBase):
        a = 'obj:' + a.id
    if isinstance(b, state_lib.StateBase):
        b = 'obj:' + b.id
    assert a == b, '%r != %r' % (a, b)


class Command(state_lib.RootMixin, state_lib.StateBase):
    log = core.ObjectProperty(CommandLog)
    status = core.Property(str)

    command_classes = {}  # type: Dict[str, Type[Command]]

    def __init__(self, state: Optional[state_lib.State] = None) -> None:
        self.__in_mutator = False

        super().__init__(state)
        if state is None:
            self.status = 'NOT_APPLIED'
            self.log = CommandLog()

    def __str__(self) -> str:
        return '%s{%s}' % (
            type(self).__name__,
            ', '.join('%s=%r' % (k, v) for k, v in sorted(self.state.items())))
    __repr__ = __str__

    def __eq__(self, other: object) -> bool:
        if self.__class__ is not other.__class__:
            return False
        for prop_name in self.list_property_names():
            if prop_name == 'id':
                continue
            if getattr(self, prop_name) != getattr(other, prop_name):
                return False
        return True

    @contextlib.contextmanager
    def __custom_mutator(self) -> Generator:
        assert not self.__in_mutator
        self.__in_mutator = True
        try:
            yield
        finally:
            self.__in_mutator = False

    @classmethod
    def register_command(cls, cmd_cls: Type['Command']) -> None:
        assert cmd_cls.__name__ not in cls.command_classes
        cls.command_classes[cmd_cls.__name__] = cmd_cls

    @classmethod
    def create(cls, command_name: str, **kwargs: Any) -> 'Command':
        cmd_cls = cls.command_classes[command_name]
        return cmd_cls(**kwargs)

    @classmethod
    def create_from_state(cls, state: state_lib.State) -> 'Command':
        cls_name = state['__class__']
        c = cls.command_classes[cls_name]
        return c(state=state)

    @property
    def is_noop(self) -> bool:
        return len(self.log.ops) == 0

    def set_property(self, obj: state_lib.StateBase, prop_name: str, new_value: Any) -> None:
        old_value = getattr(obj, prop_name)
        with self.__custom_mutator():
            setattr(obj, prop_name, new_value)

        old_slot_id = self.log.add_slot(old_value)
        new_slot_id = self.log.add_slot(new_value)
        self.log.add_operation(
            'SET_PROPERTY', obj.id, prop_name, old_slot_id, new_slot_id)

    def list_insert(
            self, obj: state_lib.StateBase, prop_name: str, index: int, new_value: Any) -> None:
        lst = getattr(obj, prop_name)
        with self.__custom_mutator():
            lst.insert(index, new_value)

        slot_id = self.log.add_slot(new_value)
        self.log.add_operation(
            'LIST_INSERT', obj.id, prop_name, index, slot_id)

    def list_delete(self, obj: state_lib.StateBase, prop_name: str, index: int) -> None:
        lst = getattr(obj, prop_name)
        old_value = lst[index]
        with self.__custom_mutator():
            del lst[index]

        slot_id = self.log.add_slot(old_value)
        self.log.add_operation(
            'LIST_DELETE', obj.id, prop_name, index, slot_id)

    def list_move(
            self, obj: state_lib.StateBase, prop_name: str, old_index: int, new_index: int) -> None:
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

    def _handle_model_change(self, obj: state_lib.StateBase, change: core.PropertyChange) -> None:
        if self.__in_mutator:
            return

        if isinstance(change, core.PropertyValueChange):
            old_slot_id = self.log.add_slot(change.old_value)
            new_slot_id = self.log.add_slot(change.new_value)

            self.log.add_operation(
                'SET_PROPERTY', obj.id, change.prop_name,
                old_slot_id, new_slot_id)

        elif isinstance(change, core.PropertyListInsert):
            slot_id = self.log.add_slot(change.new_value)
            self.log.add_operation(
                'LIST_INSERT', obj.id, change.prop_name,
                change.index, slot_id)

        elif isinstance(change, core.PropertyListDelete):
            slot_id = self.log.add_slot(change.old_value)
            self.log.add_operation(
                'LIST_DELETE', obj.id, change.prop_name, change.index,
                slot_id)

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def run(self, obj: state_lib.StateBase) -> Any:
        raise NotImplementedError

    def apply(self, obj: state_lib.StateBase) -> Any:
        assert self.status == 'NOT_APPLIED'

        listener = cast(state_lib.RootMixin, obj.root).listeners.add(
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

    def redo(self, obj: state_lib.StateBase) -> None:
        assert self.status == 'APPLIED'
        root = cast(state_lib.RootMixin, obj.root)

        for op, args in cast(Ops, self.log.ops):
            if op == 'SET_PROPERTY':
                obj_id, prop_name, old_slot_id, new_slot_id = args
                o = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                _assert_equal(getattr(o, prop_name), old_value)
                setattr(o, prop_name, new_value)

            elif op == 'LIST_INSERT':
                obj_id, prop_name, index, new_slot_id = args
                o = root.get_object(obj_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                lst = getattr(o, prop_name)
                lst.insert(index, new_value)

            elif op == 'LIST_DELETE':
                obj_id, prop_name, index, old_slot_id = args
                o = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)

                lst = getattr(o, prop_name)
                _assert_equal(lst[index], old_value)
                del lst[index]

            else:
                raise ValueError("Unknown op %s" % op)

    def undo(self, obj: state_lib.StateBase) -> None:
        assert self.status == 'APPLIED'
        root = cast(state_lib.RootMixin, obj.root)

        for op, args in reversed(cast(Ops, self.log.ops)):
            if op == 'SET_PROPERTY':
                obj_id, prop_name, old_slot_id, new_slot_id = args
                o = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                current_value = getattr(o, prop_name)
                _assert_equal(current_value, new_value)
                setattr(o, prop_name, old_value)

            elif op == 'LIST_INSERT':
                obj_id, prop_name, index, new_slot_id = args
                o = root.get_object(obj_id)
                new_value = self.log.get_slot(root.cls_map, new_slot_id)

                lst = getattr(o, prop_name)
                _assert_equal(lst[index], new_value)
                del lst[index]

            elif op == 'LIST_DELETE':
                obj_id, prop_name, index, old_slot_id = args
                o = root.get_object(obj_id)
                old_value = self.log.get_slot(root.cls_map, old_slot_id)

                lst = getattr(o, prop_name)
                lst.insert(index, old_value)

            else:
                raise ValueError("Unknown op %s" % op)


Command.register_class(CommandLog)
