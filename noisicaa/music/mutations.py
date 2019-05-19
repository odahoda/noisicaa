#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
import copy
import logging
import typing
from typing import Any, Generator

from noisicaa import audioproc
from noisicaa import value_types
from noisicaa import node_db
from noisicaa import core
from . import model_base
from . import mutations_pb2

if typing.TYPE_CHECKING:
    from . import project

logger = logging.getLogger(__name__)


def _assert_equal(a: Any, b: Any) -> None:
    if isinstance(a, model_base.ObjectBase):
        a = 'obj:%016x' % a.id
    if isinstance(b, model_base.ObjectBase):
        b = 'obj:%016x' % b.id
    assert a == b, '%r != %r' % (a, b)


class MutationList(object):
    def __init__(
            self, pool: model_base.Pool, mutation_list: mutations_pb2.MutationList
    ) -> None:
        self.__pool = pool
        self.__proto = mutation_list

    def get_slot(self, slot_id: int) -> Any:
        slot = self.__proto.slots[slot_id]
        vtype = slot.WhichOneof('value')

        if vtype == 'none':
            return None
        elif vtype == 'obj_id':
            return self.__pool[slot.obj_id]

        elif vtype == 'string_value':
            return slot.string_value
        elif vtype == 'bytes_value':
            return slot.bytes_value
        elif vtype == 'bool_value':
            return slot.bool_value
        elif vtype == 'int_value':
            return slot.int_value
        elif vtype == 'float_value':
            return slot.float_value

        elif vtype == 'musical_time':
            return audioproc.MusicalTime.from_proto(slot.musical_time)
        elif vtype == 'musical_duration':
            return audioproc.MusicalDuration.from_proto(slot.musical_duration)
        elif vtype == 'plugin_state':
            return copy.deepcopy(slot.plugin_state)
        elif vtype == 'pitch':
            return value_types.Pitch.from_proto(slot.pitch)
        elif vtype == 'key_signature':
            return value_types.KeySignature.from_proto(slot.key_signature)
        elif vtype == 'time_signature':
            return value_types.TimeSignature.from_proto(slot.time_signature)
        elif vtype == 'clef':
            return value_types.Clef.from_proto(slot.clef)
        elif vtype == 'pos2f':
            return value_types.Pos2F.from_proto(slot.pos2f)
        elif vtype == 'sizef':
            return value_types.SizeF.from_proto(slot.sizef)
        elif vtype == 'color':
            return value_types.Color.from_proto(slot.color)
        elif vtype == 'control_value':
            return value_types.ControlValue.from_proto(slot.control_value)
        elif vtype == 'node_port_properties':
            return value_types.NodePortProperties.from_proto(slot.node_port_properties)
        elif vtype == 'port_description':
            return copy.deepcopy(slot.port_description)

        else:
            raise TypeError(vtype)

    def apply_forward(self) -> None:
        for op in self.__proto.ops:
            op_type = op.WhichOneof('op')
            if op_type == 'set_property':
                o = self.__pool[op.set_property.obj_id]
                old_value = self.get_slot(op.set_property.old_slot)
                new_value = self.get_slot(op.set_property.new_slot)

                _assert_equal(getattr(o, op.set_property.prop_name), old_value)
                o.set_property_value(op.set_property.prop_name, new_value)

            elif op_type == 'list_insert':
                o = self.__pool[op.list_insert.obj_id]
                new_value = self.get_slot(op.list_insert.slot)

                lst = getattr(o, op.list_insert.prop_name)
                lst.insert(op.list_insert.index, new_value)

            elif op_type == 'list_delete':
                o = self.__pool[op.list_delete.obj_id]
                old_value = self.get_slot(op.list_delete.slot)

                lst = getattr(o, op.list_delete.prop_name)
                _assert_equal(lst[op.list_delete.index], old_value)
                del lst[op.list_delete.index]

            elif op_type == 'list_set':
                o = self.__pool[op.list_set.obj_id]
                old_value = self.get_slot(op.list_set.old_slot)
                new_value = self.get_slot(op.list_set.new_slot)

                lst = getattr(o, op.list_set.prop_name)
                _assert_equal(lst[op.list_set.index], old_value)
                lst.set(op.list_set.index, new_value)

            elif op_type == 'add_object':
                self.__pool.deserialize(op.add_object.object)

            elif op_type == 'remove_object':
                o = self.__pool[op.remove_object.object.id]
                assert o.proto == op.remove_object.object, \
                    '%s != %s' % (o.proto, op.remove_object.object)
                self.__pool.remove(op.remove_object.object.id)

            else:
                raise ValueError("Unknown op %s" % op)

    def apply_backward(self) -> None:
        for op in reversed(self.__proto.ops):
            op_type = op.WhichOneof('op')
            if op_type == 'set_property':
                o = self.__pool[op.set_property.obj_id]
                old_value = self.get_slot(op.set_property.old_slot)
                new_value = self.get_slot(op.set_property.new_slot)

                _assert_equal(getattr(o, op.set_property.prop_name), new_value)
                o.set_property_value(op.set_property.prop_name, old_value)

            elif op_type == 'list_insert':
                o = self.__pool[op.list_insert.obj_id]
                new_value = self.get_slot(op.list_insert.slot)

                lst = getattr(o, op.list_insert.prop_name)
                _assert_equal(lst[op.list_insert.index], new_value)
                del lst[op.list_insert.index]

            elif op_type == 'list_delete':
                o = self.__pool[op.list_delete.obj_id]
                old_value = self.get_slot(op.list_delete.slot)

                lst = getattr(o, op.list_delete.prop_name)
                lst.insert(op.list_delete.index, old_value)

            elif op_type == 'list_set':
                o = self.__pool[op.list_set.obj_id]
                old_value = self.get_slot(op.list_set.old_slot)
                new_value = self.get_slot(op.list_set.new_slot)

                lst = getattr(o, op.list_set.prop_name)
                _assert_equal(lst[op.list_set.index], new_value)
                lst.set(op.list_set.index, old_value)

            elif op_type == 'add_object':
                o = self.__pool[op.add_object.object.id]
                assert o.proto == op.add_object.object, \
                    '%s != %s' % (o.proto, op.add_object.object)
                self.__pool.remove(op.add_object.object.id)

            elif op_type == 'remove_object':
                self.__pool.deserialize(op.remove_object.object)

            else:
                raise ValueError("Unknown op %s" % op)


class MutationCollector(object):
    def __init__(
            self, pool: model_base.Pool, mutation_list: mutations_pb2.MutationList
    ) -> None:
        self.__pool = pool
        self.__proto = mutation_list
        self.__listener = None  # type: core.Listener

    @property
    def num_ops(self) -> int:
        return len(self.__proto.ops)

    @contextlib.contextmanager
    def collect(self) -> Generator:
        self.start()
        try:
            yield
        finally:
            self.stop()

    def start(self) -> None:
        assert self.__listener is None
        self.__listener = self.__pool.model_changed.add(self.__handle_model_change)

    def stop(self) -> None:
        assert self.__listener is not None
        self.__listener.remove()
        self.__listener = None

    def clear(self) -> None:
        self.__proto.Clear()

    def __handle_model_change(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyValueChange):
            old_slot_id = self.__add_slot(change.old_value)
            new_slot_id = self.__add_slot(change.new_value)

            self.__add_operation(mutations_pb2.MutationList.Op(
                set_property=mutations_pb2.MutationList.SetProperty(
                    obj_id=change.obj.id,
                    prop_name=change.prop_name,
                    old_slot=old_slot_id,
                    new_slot=new_slot_id)))

        elif isinstance(change, model_base.PropertyListInsert):
            slot_id = self.__add_slot(change.new_value)
            self.__add_operation(mutations_pb2.MutationList.Op(
                list_insert=mutations_pb2.MutationList.ListInsert(
                    obj_id=change.obj.id,
                    prop_name=change.prop_name,
                    index=change.index,
                    slot=slot_id)))

        elif isinstance(change, model_base.PropertyListDelete):
            slot_id = self.__add_slot(change.old_value)
            self.__add_operation(mutations_pb2.MutationList.Op(
                list_delete=mutations_pb2.MutationList.ListDelete(
                    obj_id=change.obj.id,
                    prop_name=change.prop_name,
                    index=change.index,
                    slot=slot_id)))

        elif isinstance(change, model_base.PropertyListSet):
            old_slot_id = self.__add_slot(change.old_value)
            new_slot_id = self.__add_slot(change.new_value)
            self.__add_operation(mutations_pb2.MutationList.Op(
                list_set=mutations_pb2.MutationList.ListSet(
                    obj_id=change.obj.id,
                    prop_name=change.prop_name,
                    index=change.index,
                    old_slot=old_slot_id,
                    new_slot=new_slot_id)))

        elif isinstance(change, model_base.ObjectAdded):
            self.__add_operation(mutations_pb2.MutationList.Op(
                add_object=mutations_pb2.MutationList.AddObject(
                    object=change.obj.proto)))

        elif isinstance(change, model_base.ObjectRemoved):
            self.__add_operation(mutations_pb2.MutationList.Op(
                remove_object=mutations_pb2.MutationList.RemoveObject(
                    object=change.obj.proto)))

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_slot(self, value: Any) -> int:
        slot = self.__proto.slots.add()
        if value is None:
            slot.none = True
        elif isinstance(value, model_base.ObjectBase):
            slot.obj_id = value.id

        elif isinstance(value, str):
            slot.string_value = value
        elif isinstance(value, bytes):
            slot.bytes_value = value
        elif isinstance(value, bool):
            slot.bool_value = value
        elif isinstance(value, int):
            slot.int_value = value
        elif isinstance(value, float):
            slot.float_value = value

        elif isinstance(value, audioproc.MusicalTime):
            slot.musical_time.CopyFrom(value.to_proto())
        elif isinstance(value, audioproc.MusicalDuration):
            slot.musical_duration.CopyFrom(value.to_proto())
        elif isinstance(value, audioproc.PluginState):
            slot.plugin_state.CopyFrom(value)
        elif isinstance(value, value_types.Pitch):
            slot.pitch.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.KeySignature):
            slot.key_signature.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.TimeSignature):
            slot.time_signature.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.Clef):
            slot.clef.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.Pos2F):
            slot.pos2f.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.SizeF):
            slot.sizef.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.Color):
            slot.color.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.ControlValue):
            slot.control_value.CopyFrom(value.to_proto())
        elif isinstance(value, value_types.NodePortProperties):
            slot.node_port_properties.CopyFrom(value.to_proto())
        elif isinstance(value, node_db.PortDescription):
            slot.port_description.CopyFrom(value)

        else:
            raise TypeError(type(value))

        return len(self.__proto.slots) - 1

    def __add_operation(self, op: mutations_pb2.MutationList.Op) -> None:
        p = self.__proto.ops.add()
        p.CopyFrom(op)
