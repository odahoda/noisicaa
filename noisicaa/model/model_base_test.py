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

import collections
from typing import cast, Any, Optional, Type, Iterator, Dict, List, Tuple  # pylint: disable=unused-import

from google.protobuf import message as protobuf  # pylint: disable=unused-import

from noisidev import unittest
from noisicaa import core
from . import model_base
from . import model_base_pb2
from . import model_base_test_pb2


class Pool(collections.UserDict, model_base.AbstractPool[model_base.ObjectBase]):
    @property
    def objects(self) -> Iterator[model_base.ObjectBase]:
        raise NotImplementedError

    def create(  # pylint: disable=redefined-builtin
            self, cls: Type[model_base.OBJECT], id: Optional[int] = None, **kwargs: Any
    ) -> model_base.OBJECT:
        raise NotImplementedError


class Proto(model_base.ProtoValue):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Proto(%d, %d)' % (self.a, self.b)

    def __eq__(self, other):
        return (
            isinstance(other, Proto)
            and self.a == other.a
            and self.b == other.b)

    def to_proto(self):
        return model_base_test_pb2.Proto(a=self.a, b=self.b)

    @classmethod
    def from_proto(cls, pb):
        return Proto(pb.a, pb.b)


class GrandChild(model_base.ObjectBase):
    class GrandChildSpec(model_base.ObjectSpec):
        proto_type = 'grand_child'


class Child(model_base.ObjectBase):
    class ChildSpec(model_base.ObjectSpec):
        proto_type = 'child'
        proto_ext = model_base_test_pb2.child  # type: ignore
        child = model_base.ObjectProperty(GrandChild)
        value = model_base.Property(str, allow_none=True)

    def __repr__(self):
        return 'Child(%d)' % self.id

    def create(self, *, value=None, **kwargs: Any) -> None:
        super().create(**kwargs)
        if value is not None:
            self.value = value

    @property
    def child(self):
        return self.get_property_value('child')

    @child.setter
    def child(self, value) -> None:
        self.set_property_value('child', value)

    @property
    def value(self):
        return self.get_property_value('value')

    @value.setter
    def value(self, value) -> None:
        self.set_property_value('value', value)


class Root(model_base.ObjectBase):
    class RootSpec(model_base.ObjectSpec):
        proto_type = 'root'
        proto_ext = model_base_test_pb2.root  # type: ignore

        string_value = model_base.Property(str)
        int_value = model_base.Property(int, allow_none=True)
        float_value = model_base.Property(float, default=12.2)
        string_list = model_base.ListProperty(str)
        child_value = model_base.ObjectProperty(Child)
        child_list = model_base.ObjectListProperty(Child)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.change = core.Callback[model_base.PropertyChange]()

    def create(self, *, string_value=None, **kwargs: Any) -> None:
        super().create(**kwargs)
        if string_value is not None:
            self.string_value = string_value

    @property
    def string_value(self):
        return self.get_property_value('string_value')

    @string_value.setter
    def string_value(self, value) -> None:
        self.set_property_value('string_value', value)

    @property
    def int_value(self):
        return self.get_property_value('int_value')

    @int_value.setter
    def int_value(self, value) -> None:
        self.set_property_value('int_value', value)

    @property
    def float_value(self):
        return self.get_property_value('float_value')

    @float_value.setter
    def float_value(self, value) -> None:
        self.set_property_value('float_value', value)

    @property
    def string_list(self):
        return self.get_property_value('string_list')

    @property
    def child_value(self):
        return self.get_property_value('child_value')

    @child_value.setter
    def child_value(self, value) -> None:
        self.set_property_value('child_value', value)

    @property
    def child_list(self):
        return self.get_property_value('child_list')

    def property_changed(self, change):
        self.change.call(change)


class PropertyChangeCollector(object):
    def __init__(self, obj, prop_name):
        self.prop_name = prop_name
        self.changes = []  # type: List[Tuple[Any]]

        obj.change.add(self.on_change)

    def on_change(self, change):
        if change.prop_name != self.prop_name:
            return

        if isinstance(change, model_base.PropertyValueChange):
            if isinstance(change.old_value, model_base.ObjectBase):
                old_value = change.old_value.id
            else:
                old_value = change.old_value
            if isinstance(change.new_value, model_base.ObjectBase):
                new_value = change.new_value.id
            else:
                new_value = change.new_value
            self.changes.append(('change', old_value, new_value))
        elif isinstance(change, model_base.PropertyListDelete):
            if isinstance(change.old_value, model_base.ObjectBase):
                old_value = change.old_value.id
            else:
                old_value = change.old_value
            self.changes.append(('delete', change.index, old_value))
        elif isinstance(change, model_base.PropertyListInsert):
            if isinstance(change.new_value, model_base.ObjectBase):
                new_value = change.new_value.id
            else:
                new_value = change.new_value
            self.changes.append(('insert', change.index, new_value))
        else:
            raise TypeError(type(change).__name__)


class PropertyChangeTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()

    def test_property_value_change(self):
        change = model_base.PropertyValueChange(self.obj, 'field', 'old', 'new')
        self.assertIs(change.obj, self.obj)
        self.assertEqual(change.prop_name, 'field')
        self.assertEqual(change.old_value, 'old')
        self.assertEqual(change.new_value, 'new')
        self.assertEqual(str(change), "<PropertyValueChange new='new' old='old'>")

    def test_property_list_insert(self):
        change = model_base.PropertyListInsert(self.obj, 'field', 12, 'new')
        self.assertIs(change.obj, self.obj)
        self.assertEqual(change.prop_name, 'field')
        self.assertEqual(change.index, 12)
        self.assertEqual(change.new_value, 'new')
        self.assertEqual(str(change), "<PropertyListInsert index=12 new='new'>")

    def test_property_list_delete(self):
        change = model_base.PropertyListDelete(self.obj, 'field', 12, 'old')
        self.assertIs(change.obj, self.obj)
        self.assertEqual(change.prop_name, 'field')
        self.assertEqual(change.index, 12)
        self.assertEqual(change.old_value, 'old')
        self.assertEqual(str(change), "<PropertyListDelete index=12 old='old'>")


class ObjectTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()

    def test_create(self):
        pb = model_base_pb2.ObjectBase()
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

    def test_proto(self):
        pb = model_base_pb2.ObjectBase()
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()
        self.assertIs(obj.proto, pb)

    def test_id(self):
        pb = model_base_pb2.ObjectBase(id=124)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()
        self.assertEqual(obj.id, 124)

    def test_str(self):
        pb = model_base_pb2.ObjectBase(id=124)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()
        self.assertEqual(str(obj), '<Root id=124>')

    def test_get_property(self):
        pb = model_base_pb2.ObjectBase(id=124)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        self.assertIs(obj.get_property('id'), model_base.ObjectBase.ObjectBaseSpec.id)
        self.assertIs(obj.get_property('string_value'), Root.RootSpec.string_value)

        with self.assertRaises(AttributeError):
            obj.get_property('does_not_exist')

    def test_list_properties(self):
        pb = model_base_pb2.ObjectBase(id=124)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        self.assertEqual(
            {prop.name for prop in obj.list_properties()},
            {'id', 'string_value', 'int_value', 'float_value', 'string_list', 'child_value',
             'child_list'})

    def test_list_property_names(self):
        pb = model_base_pb2.ObjectBase(id=124)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        self.assertEqual(
            set(obj.list_property_names()),
            {'id', 'string_value', 'int_value', 'float_value', 'string_list', 'child_value',
             'child_list'})

    def test_list_children(self):
        for i in range(3):
            c = Child(pb=model_base_pb2.ObjectBase(id=100 + i), pool=self.pool)
            c.create()
            c.setup()
            c.setup_complete()
            self.pool[c.id] = c

        obj = Root(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        obj.child_value = self.pool[100]
        obj.child_list.append(self.pool[101])
        obj.child_list.append(self.pool[102])

        self.assertEqual(
            {child.id for child in obj.list_children()},
            {100, 101, 102})

    def test_list_children_unset_value(self):
        for i in range(3):
            c = Child(pb=model_base_pb2.ObjectBase(id=100 + i), pool=self.pool)
            c.create()
            c.setup()
            c.setup_complete()
            self.pool[c.id] = c

        obj = Root(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        obj.child_list.append(self.pool[101])
        obj.child_list.append(self.pool[102])

        self.assertEqual(
            {child.id for child in obj.list_children()},
            {101, 102})

    def test_object_list(self):
        for i in range(4):
            c = Child(pb=model_base_pb2.ObjectBase(id=100 + i), pool=self.pool)
            c.create()
            c.setup()
            c.setup_complete()
            self.pool[c.id] = c

        obj = Root(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        obj.child_list.append(self.pool[100])
        obj.child_list.append(self.pool[101])
        obj.child_list.append(self.pool[102])
        obj.child_list.append(self.pool[103])

        self.assertEqual(self.pool[100].index, 0)
        self.assertEqual(self.pool[101].index, 1)
        self.assertEqual(self.pool[102].index, 2)
        self.assertEqual(self.pool[103].index, 3)

        self.assertTrue(self.pool[100].is_first)
        self.assertFalse(self.pool[101].is_first)
        self.assertFalse(self.pool[102].is_first)
        self.assertFalse(self.pool[103].is_first)

        self.assertFalse(self.pool[100].is_last)
        self.assertFalse(self.pool[101].is_last)
        self.assertFalse(self.pool[102].is_last)
        self.assertTrue(self.pool[103].is_last)

        with self.assertRaises(IndexError):
            self.pool[100].prev_sibling  # pylint: disable=pointless-statement
        self.assertIs(self.pool[101].prev_sibling, self.pool[100])
        self.assertIs(self.pool[102].prev_sibling, self.pool[101])
        self.assertIs(self.pool[103].prev_sibling, self.pool[102])

        self.assertIs(self.pool[100].next_sibling, self.pool[101])
        self.assertIs(self.pool[101].next_sibling, self.pool[102])
        self.assertIs(self.pool[102].next_sibling, self.pool[103])
        with self.assertRaises(IndexError):
            self.pool[103].next_sibling  # pylint: disable=pointless-statement

    def test_not_attached(self):
        obj = Root(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        with self.assertRaises(ValueError):
            obj.index  # pylint: disable=pointless-statement

        with self.assertRaises(ValueError):
            obj.is_first  # pylint: disable=pointless-statement

        with self.assertRaises(ValueError):
            obj.is_last  # pylint: disable=pointless-statement

        with self.assertRaises(ValueError):
            obj.prev_sibling  # pylint: disable=pointless-statement

        with self.assertRaises(ValueError):
            obj.next_sibling  # pylint: disable=pointless-statement

    def test_properties(self):
        pb = model_base_pb2.ObjectBase()
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        obj.string_value = 'abc'
        self.assertEqual(obj.string_value, 'abc')

        self.assertIsNone(obj.int_value)
        obj.int_value = 12
        self.assertEqual(obj.int_value, 12)

        self.assertEqual(obj.float_value, 12.2)
        obj.float_value = 2.5
        self.assertEqual(obj.float_value, 2.5)

        self.assertEqual(obj.string_list, [])
        obj.string_list.append('a')
        self.assertEqual(obj.string_list, ['a'])

    def test_walk_object_tree(self):
        obj = Root(pb=model_base_pb2.ObjectBase(id=100), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        for i in range(3):
            c = Child(pb=model_base_pb2.ObjectBase(id=110 + i), pool=self.pool)
            c.create()
            c.setup()
            c.setup_complete()
            self.pool[c.id] = c

        for i in range(2):
            gc = GrandChild(pb=model_base_pb2.ObjectBase(id=120 + i), pool=self.pool)
            gc.create()
            gc.setup()
            gc.setup_complete()
            self.pool[gc.id] = gc

        obj.child_value = self.pool[110]
        obj.child_value.child = self.pool[121]
        obj.child_list.append(self.pool[111])
        obj.child_list.append(self.pool[112])
        obj.child_list[1].child = self.pool[120]

        ids = [o.id for o in obj.walk_object_tree()]
        self.assertEqual(set(ids), {100, 110, 111, 112, 120, 121})
        index = {id: idx for idx, id in enumerate(ids)}
        self.assertLess(index[110], index[100])
        self.assertLess(index[111], index[100])
        self.assertLess(index[112], index[100])
        self.assertLess(index[121], index[110])
        self.assertLess(index[120], index[112])

    def test_serialize(self):
        pb = model_base_pb2.ObjectBase(id=123)
        obj = Root(pb=pb, pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()

        serialized = obj.serialize()
        self.assertIsInstance(serialized, model_base_pb2.ObjectTree)
        self.assertEqual(serialized.root, obj.id)


class PropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = None
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_changes(self):
        changes = PropertyChangeCollector(self.obj, 'string_value')

        prop = model_base.Property(str, allow_none=True)
        prop.name = 'string_value'

        prop.set_value(self.obj, self.pb, self.pool, '123')
        prop.set_value(self.obj, self.pb, self.pool, 'abc')
        prop.set_value(self.obj, self.pb, self.pool, 'abc')
        prop.set_value(self.obj, self.pb, self.pool, None)

        self.assertEqual(
            changes.changes,
            [('change', None, '123'),
             ('change', '123', 'abc'),
             ('change', 'abc', None)])

    def test_not_none(self):
        prop = model_base.Property(str)
        prop.name = 'string_value'
        with self.assertRaises(ValueError):
            prop.get_value(self.obj, self.pb, self.pool)
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_allow_none(self):
        prop = model_base.Property(str, allow_none=True)
        prop.name = 'string_value'
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))
        prop.set_value(self.obj, self.pb, self.pool, '123')
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), '123')
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))

    def test_default_not_none(self):
        prop = model_base.Property(str, default='abc')
        prop.name = 'string_value'
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), 'abc')
        prop.set_value(self.obj, self.pb, self.pool, '123')
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), '123')
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_default_allow_none(self):
        prop = model_base.Property(str, allow_none=True, default='abc')
        prop.name = 'string_value'
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), 'abc')
        prop.set_value(self.obj, self.pb, self.pool, '123')
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), '123')
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), 'abc')

    def test_type(self):
        prop = model_base.Property(str)
        prop.name = 'string_value'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, 123)  # type: ignore


class ProtoPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = None
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_changes(self):
        changes = PropertyChangeCollector(self.obj, 'proto_value')

        prop = model_base.ProtoProperty(model_base_test_pb2.Proto, allow_none=True)
        prop.name = 'proto_value'

        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=1, b=2))
        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=2, b=3))
        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=2, b=3))
        prop.set_value(self.obj, self.pb, self.pool, None)

        self.assertEqual(
            changes.changes,
            [('change', None, model_base_test_pb2.Proto(a=1, b=2)),
             ('change', model_base_test_pb2.Proto(a=1, b=2), model_base_test_pb2.Proto(a=2, b=3)),
             ('change', model_base_test_pb2.Proto(a=2, b=3), None)])

    def test_not_none(self):
        prop = model_base.ProtoProperty(model_base_test_pb2.Proto)
        prop.name = 'proto_value'
        with self.assertRaises(ValueError):
            prop.get_value(self.obj, self.pb, self.pool)
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_allow_none(self):
        prop = model_base.ProtoProperty(model_base_test_pb2.Proto, allow_none=True)
        prop.name = 'proto_value'
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))
        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=1, b=2))
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=1, b=2))
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))

    def test_default_not_none(self):
        prop = model_base.ProtoProperty(
            model_base_test_pb2.Proto, default=model_base_test_pb2.Proto(a=2, b=3))
        prop.name = 'proto_value'
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=2, b=3))
        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=1, b=2))
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=1, b=2))
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_default_allow_none(self):
        prop = model_base.ProtoProperty(
            model_base_test_pb2.Proto, allow_none=True, default=model_base_test_pb2.Proto(a=2, b=3))
        prop.name = 'proto_value'
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=2, b=3))
        prop.set_value(self.obj, self.pb, self.pool, model_base_test_pb2.Proto(a=1, b=2))
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=1, b=2))
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertEqual(
            prop.get_value(self.obj, self.pb, self.pool), model_base_test_pb2.Proto(a=2, b=3))

    def test_type(self):
        prop = model_base.ProtoProperty(model_base_test_pb2.Proto)
        prop.name = 'proto_value'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, 123)  # type: ignore


class WrappedProtoPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = None
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_changes(self):
        changes = PropertyChangeCollector(self.obj, 'proto_value')

        prop = model_base.WrappedProtoProperty(Proto, allow_none=True)
        prop.name = 'proto_value'

        prop.set_value(self.obj, self.pb, self.pool, Proto(1, 2))
        prop.set_value(self.obj, self.pb, self.pool, Proto(2, 3))
        prop.set_value(self.obj, self.pb, self.pool, Proto(2, 3))
        prop.set_value(self.obj, self.pb, self.pool, None)

        self.assertEqual(
            changes.changes,
            [('change', None, Proto(1, 2)),
             ('change', Proto(1, 2), Proto(2, 3)),
             ('change', Proto(2, 3), None)])

    def test_not_none(self):
        prop = model_base.WrappedProtoProperty(Proto)
        prop.name = 'proto_value'
        with self.assertRaises(ValueError):
            prop.get_value(self.obj, self.pb, self.pool)
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_allow_none(self):
        prop = model_base.WrappedProtoProperty(Proto, allow_none=True)
        prop.name = 'proto_value'
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))
        prop.set_value(self.obj, self.pb, self.pool, Proto(1, 2))
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(1, 2))
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))

    def test_default_not_none(self):
        prop = model_base.WrappedProtoProperty(Proto, default=Proto(2, 3))
        prop.name = 'proto_value'
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(2, 3))
        prop.set_value(self.obj, self.pb, self.pool, Proto(1, 2))
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(1, 2))
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_default_allow_none(self):
        prop = model_base.WrappedProtoProperty(Proto, allow_none=True, default=Proto(2, 3))
        prop.name = 'proto_value'
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(2, 3))
        prop.set_value(self.obj, self.pb, self.pool, Proto(1, 2))
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(1, 2))
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertEqual(prop.get_value(self.obj, self.pb, self.pool), Proto(2, 3))

    def test_type(self):
        prop = model_base.WrappedProtoProperty(Proto)
        prop.name = 'proto_value'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, 123)  # type: ignore


class ObjectPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

        self.child = Child(pb=model_base_pb2.ObjectBase(id=123), pool=self.pool)
        self.child.create()
        self.child.setup()
        self.child.setup_complete()
        self.pool[self.child.id] = self.child

        self.child2 = Child(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        self.child2.create()
        self.child2.setup()
        self.child2.setup_complete()
        self.pool[self.child2.id] = self.child2

        self.grandchild = GrandChild(pb=model_base_pb2.ObjectBase(id=125), pool=self.pool)
        self.grandchild.create()
        self.grandchild.setup()
        self.grandchild.setup_complete()
        self.pool[self.grandchild.id] = self.grandchild

    def test_changes(self):
        changes = PropertyChangeCollector(self.obj, 'child_value')

        prop = model_base.ObjectProperty(Child, allow_none=True)
        prop.name = 'child_value'

        prop.set_value(self.obj, self.pb, self.pool, self.child)
        prop.set_value(self.obj, self.pb, self.pool, self.child2)
        prop.set_value(self.obj, self.pb, self.pool, self.child2)
        prop.set_value(self.obj, self.pb, self.pool, None)

        self.assertEqual(
            changes.changes,
            [('change', None, 123),
             ('change', 123, 124),
             ('change', 124, None)])

    def test_not_none(self):
        prop = model_base.ObjectProperty(Child)
        prop.name = 'child_value'
        with self.assertRaises(ValueError):
            prop.get_value(self.obj, self.pb, self.pool)
        with self.assertRaises(ValueError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_allow_none(self):
        prop = model_base.ObjectProperty(Child, allow_none=True)
        prop.name = 'child_value'
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))
        prop.set_value(self.obj, self.pb, self.pool, self.child)
        self.assertIs(prop.get_value(self.obj, self.pb, self.pool), self.child)
        prop.set_value(self.obj, self.pb, self.pool, None)
        self.assertIsNone(prop.get_value(self.obj, self.pb, self.pool))

    def test_ownership(self):
        prop = model_base.ObjectProperty(Child, allow_none=True)
        prop.name = 'child_value'

        self.child2.child = self.grandchild
        self.assertFalse(self.grandchild.is_child_of(self.obj))

        self.assertFalse(self.child.is_attached)
        self.assertIsNone(self.child.parent)
        self.assertFalse(self.child.is_child_of(self.obj))
        prop.set_value(self.obj, self.pb, self.pool, self.child)
        self.assertTrue(self.child.is_attached)
        self.assertIs(self.child.parent, self.obj)
        self.assertTrue(self.child.is_child_of(self.obj))
        self.assertFalse(self.grandchild.is_child_of(self.obj))

        prop.set_value(self.obj, self.pb, self.pool, self.child2)
        self.assertFalse(self.child.is_attached)
        self.assertIsNone(self.child.parent)
        self.assertFalse(self.child.is_child_of(self.obj))
        self.assertTrue(self.child2.is_attached)
        self.assertIs(self.child2.parent, self.obj)
        self.assertTrue(self.child2.is_child_of(self.obj))
        self.assertTrue(self.grandchild.is_child_of(self.obj))

    def test_type(self):
        prop = model_base.ObjectProperty(Child)
        prop.name = 'child_value'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, 123)  # type: ignore


class ListPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_set_value(self):
        prop = model_base.ListProperty(str)
        prop.name = 'string_list'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_get_value(self):
        prop = model_base.ListProperty(str)
        prop.name = 'string_list'
        lst = prop.get_value(self.obj, self.pb, self.pool)
        self.assertIsInstance(lst, model_base.SimpleList)


class WrappedProtoListPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_set_value(self):
        prop = model_base.WrappedProtoListProperty(Proto)
        prop.name = 'proto_list'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_get_value(self):
        prop = model_base.WrappedProtoListProperty(Proto)
        prop.name = 'proto_list'
        lst = prop.get_value(self.obj, self.pb, self.pool)
        self.assertIsInstance(lst, model_base.WrappedProtoList)


class ObjectListPropertyTest(unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        self.obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        self.obj.create()
        self.obj.setup()
        self.obj.setup_complete()
        self.pb = self.obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore

    def test_set_value(self):
        prop = model_base.ObjectListProperty(Child)
        prop.name = 'child_list'
        with self.assertRaises(TypeError):
            prop.set_value(self.obj, self.pb, self.pool, None)

    def test_get_value(self):
        prop = model_base.ObjectListProperty(Child)
        prop.name = 'child_list'
        lst = prop.get_value(self.obj, self.pb, self.pool)
        self.assertIsInstance(lst, model_base.ObjectList)

    def test_ownership(self):
        prop = model_base.ObjectListProperty(Child)
        prop.name = 'child_list'
        lst = prop.get_value(self.obj, self.pb, self.pool)

        child1 = Child(pb=model_base_pb2.ObjectBase(id=123), pool=self.pool)
        child1.create()
        child1.setup()
        child1.setup_complete()
        self.pool[child1.id] = child1

        child2 = Child(pb=model_base_pb2.ObjectBase(id=124), pool=self.pool)
        child2.create()
        child2.setup()
        child2.setup_complete()
        self.pool[child2.id] = child2

        grandchild = GrandChild(pb=model_base_pb2.ObjectBase(id=125), pool=self.pool)
        grandchild.create()
        grandchild.setup()
        grandchild.setup_complete()
        self.pool[grandchild.id] = grandchild

        child2.child = grandchild
        self.assertFalse(grandchild.is_child_of(self.obj))

        self.assertFalse(child1.is_attached)
        self.assertIsNone(child1.parent)
        self.assertFalse(child1.is_child_of(self.obj))
        lst.append(child1)
        self.assertTrue(child1.is_attached)
        self.assertIs(child1.parent, self.obj)
        self.assertTrue(child1.is_child_of(self.obj))
        self.assertFalse(grandchild.is_child_of(self.obj))

        lst[0] = child2
        self.assertFalse(child1.is_attached)
        self.assertIsNone(child1.parent)
        self.assertFalse(child1.is_child_of(self.obj))
        self.assertTrue(child2.is_attached)
        self.assertIs(child2.parent, self.obj)
        self.assertTrue(child2.is_child_of(self.obj))
        self.assertTrue(grandchild.is_child_of(self.obj))


class ListMixin(object):
    def create_list(self):
        raise NotImplementedError

    def create_elements(self):
        raise NotImplementedError

    def create_bad_element(self):
        raise NotImplementedError

    def test_mutations(self):
        lst = self.create_list()
        e1, e2, e3, e4, e5 = self.create_elements()

        self.assertEqual(len(lst), 0)
        self.assertEqual(lst, [])

        lst.append(e1)
        self.assertEqual(lst, [e1])

        lst.extend([e2, e3, e4])
        self.assertEqual(lst, [e1, e2, e3, e4])

        self.assertEqual(lst[0], e1)
        self.assertEqual(lst[1], e2)
        self.assertEqual(lst[3], e4)
        self.assertEqual(lst[-1], e4)
        self.assertEqual(lst[-3], e2)

        del lst[1]
        self.assertEqual(lst, [e1, e3, e4])
        lst.insert(2, e5)
        self.assertEqual(lst, [e1, e3, e5, e4])

        lst.clear()
        self.assertEqual(lst, [])

    def test_changes(self):
        lst = self.create_list()
        e1, e2, e3, e4 = self.create_elements()[:4]

        def value_or_id(val):
            if isinstance(val, model_base.ObjectBase):
                return val.id
            return val

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        lst.append(e1)
        self.assertEqual(
            changes.changes,
            [('insert', 0, value_or_id(e1))])

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        lst[0] = e2
        self.assertEqual(
            changes.changes,
            [('delete', 0, value_or_id(e1)),
             ('insert', 0, value_or_id(e2))])

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        lst.insert(0, e3)
        self.assertEqual(
            changes.changes,
            [('insert', 0, value_or_id(e3))])

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        lst.append(e4)
        self.assertEqual(
            changes.changes,
            [('insert', 2, value_or_id(e4))])

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        del lst[1]
        self.assertEqual(
            changes.changes,
            [('delete', 1, value_or_id(e2))])

        changes = PropertyChangeCollector(lst._instance, lst._prop_name)
        lst.clear()
        self.assertEqual(
            changes.changes,
            [('delete', 1, value_or_id(e4)),
             ('delete', 0, value_or_id(e3))])

    def test_slice(self):
        lst = self.create_list()
        e1, e2, e3, e4, e5 = self.create_elements()
        lst.extend([e1, e2, e3, e4, e5])

        self.assertEqual(lst[2:4], [e3, e4])
        self.assertEqual(lst[:4], [e1, e2, e3, e4])
        self.assertEqual(lst[2:], [e3, e4, e5])
        self.assertEqual(lst[:], [e1, e2, e3, e4, e5])
        self.assertEqual(lst[::2], [e1, e3, e5])
        self.assertEqual(lst[-3:], [e3, e4, e5])
        self.assertEqual(lst[:-3], [e1, e2])

        del lst[4]
        del lst[3]
        lst[1:3] = [e4, e5]
        self.assertEqual(lst, [e1, e4, e5])

    def test_type(self):
        lst = self.create_list()
        good = self.create_elements()[0]
        bad = self.create_bad_element()

        with self.assertRaises(TypeError):
            lst.append(bad)
        lst.append(good)
        with self.assertRaises(TypeError):
            lst[0] = bad

    def test_bounds(self):
        lst = self.create_list()
        e1, e2, e3, e4, e5 = self.create_elements()
        lst.extend([e1, e2, e3, e4])

        with self.assertRaises(IndexError):
            lst[4]  # pylint: disable=pointless-statement

        with self.assertRaises(IndexError):
            lst[-5]  # pylint: disable=pointless-statement

        with self.assertRaises(IndexError):
            lst.insert(5, e5)

        with self.assertRaises(IndexError):
            lst.insert(-1, e5)

    def test_compare(self):
        e1, e2 = self.create_elements()[:2]

        lst1 = self.create_list()
        lst1.append(e1)
        lst1.append(e2)
        lst2 = self.create_list()
        lst2.append(e1)
        lst2.append(e2)
        self.assertTrue(lst1 == lst2)

        del lst1[0]
        self.assertFalse(lst1 == lst2)

        lst1.append(e1)
        self.assertFalse(lst1 == lst2)

        with self.assertRaises(TypeError):
            lst1 == 123  # pylint: disable=pointless-statement


class SimpleListTest(ListMixin, unittest.TestCase):
    def create_list(self):
        obj = Root(pb=model_base_pb2.ObjectBase(), pool={})
        obj.create()
        obj.setup()
        obj.setup_complete()
        pb = obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore
        return model_base.SimpleList(obj, 'string_list', pb.string_list, str)

    def create_elements(self):
        return ('a', 'b', 'c', 'd', 'e')

    def create_bad_element(self):
        return 123

    def test_repr(self):
        lst = self.create_list()
        lst.append('a')
        lst.append('b')
        self.assertEqual(repr(lst), "['a', 'b']")


class WrappedProtoListTest(ListMixin, unittest.TestCase):
    def create_list(self):
        obj = Root(pb=model_base_pb2.ObjectBase(), pool={})
        obj.create()
        obj.setup()
        obj.setup_complete()
        pb = obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore
        return model_base.WrappedProtoList(obj, 'proto_list', pb.proto_list, Proto)

    def create_elements(self):
        return (Proto(1, 2), Proto(2, 3), Proto(3, 4), Proto(4, 5), Proto(5, 6))

    def create_bad_element(self):
        return 123

    def test_repr(self):
        lst = self.create_list()
        lst.append(Proto(1, 2))
        lst.append(Proto(2, 3))
        self.assertEqual(repr(lst), "[Proto(1, 2), Proto(2, 3)]")


class ObjectListTest(ListMixin, unittest.TestCase):
    def setup_testcase(self):
        self.pool = Pool()
        for i in range(5):
            child = Child(pb=model_base_pb2.ObjectBase(id=100 + i), pool=self.pool)
            child.create()
            child.setup()
            child.setup_complete()
            self.pool[child.id] = child

    def create_list(self):
        obj = Root(pb=model_base_pb2.ObjectBase(), pool=self.pool)
        obj.create()
        obj.setup()
        obj.setup_complete()
        pb = obj.proto.Extensions[model_base_test_pb2.root]  # type: ignore
        return model_base.ObjectList(obj, 'child_list', pb.child_list, Child, self.pool)

    def create_elements(self):
        return [self.pool[100 + i] for i in range(5)]

    def create_bad_element(self):
        return 123

    def test_repr(self):
        lst = self.create_list()
        lst.append(self.pool[100])
        lst.append(self.pool[101])
        self.assertEqual(repr(lst), "[Child(100), Child(101)]")

    # Objects can only be owned by one list, so comparing ObjectLists doesn't make sense.
    test_compare = None


class PoolTest(unittest.TestCase):
    def test_register_class(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)
        pool.register_class(Child)

        with self.assertRaises(AssertionError):
            pool.register_class(Root)

    def test_create(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        obj = pool.create(Root)
        self.assertIsInstance(obj, Root)
        self.assertIsNotNone(obj.id)

    def test_create_with_id(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        obj = pool.create(Root, id=100)
        self.assertEqual(obj.id, 100)

    def test_create_with_args(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        obj = pool.create(Root, id=100, string_value='foo')
        self.assertEqual(obj.string_value, 'foo')

    def test_get(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        obj = pool.create(Root, id=100)
        self.assertIs(pool[100], obj)

    def test_del(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        pool.create(Root, id=100)
        del pool[100]
        with self.assertRaises(KeyError):
            pool[100]  # pylint: disable=pointless-statement

    def test_deserialize(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Child)

        obj1 = pool.create(Child, id=100, value='foo')
        pb = obj1.proto

        with self.assertRaises(AssertionError):
            pool.deserialize(pb)

        del pool[100]

        obj2 = cast(Child, pool.deserialize(pb))
        self.assertIsInstance(obj2, Child)
        self.assertEqual(obj2.id, 100)
        self.assertEqual(obj2.value, 'foo')

    def test_deserialize_tree(self):
        pool1 = model_base.Pool[model_base.ObjectBase]()
        pool1.register_class(Root)
        pool1.register_class(Child)

        root1 = pool1.create(Root, id=100, string_value='foo')
        root1.child_value = pool1.create(Child, id=110)
        root1.child_list.append(pool1.create(Child, id=111))
        root1.child_list.append(pool1.create(Child, id=112))

        serialized = root1.serialize()

        pool2 = model_base.Pool[model_base.ObjectBase]()
        pool2.register_class(Root)
        pool2.register_class(Child)

        root2 = cast(Root, pool2.deserialize_tree(serialized))
        self.assertIsInstance(root2, Root)
        self.assertEqual(root2.id, 100)
        self.assertEqual(root2.string_value, 'foo')
        self.assertIsInstance(root2.child_value, Child)
        self.assertEqual(root2.child_value.id, 110)
        self.assertIsInstance(root2.child_list[0], Child)
        self.assertEqual(root2.child_list[0].id, 111)
        self.assertIsInstance(root2.child_list[1], Child)
        self.assertEqual(root2.child_list[1].id, 112)

    def test_clone_tree(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)
        pool.register_class(Child)

        root1 = pool.create(Root, id=100, string_value='foo')
        root1.child_value = pool.create(Child, id=110)
        root1.child_list.append(pool.create(Child, id=111))
        root1.child_list.append(pool.create(Child, id=112))

        serialized = root1.serialize()

        root2 = cast(Root, pool.clone_tree(serialized))
        self.assertIsInstance(root2, Root)
        self.assertIsNot(root2, root1)
        self.assertEqual(root2.string_value, 'foo')
        self.assertIsInstance(root2.child_value, Child)
        self.assertIs(root2.child_value.parent, root2)
        self.assertIsInstance(root2.child_list[0], Child)
        self.assertIs(root2.child_list[0].parent, root2)
        self.assertIsInstance(root2.child_list[1], Child)
        self.assertIs(root2.child_list[1].parent, root2)

    def test_iter(self):
        pool = model_base.Pool[model_base.ObjectBase]()
        pool.register_class(Root)

        pool.create(Root, id=100, string_value='foo')
        pool.create(Root, id=101, string_value='bar')

        self.assertEqual(len(pool), 2)

        self.assertEqual(
            {obj_id for obj_id in pool},
            {100, 101})

        self.assertEqual(
            {(obj.id, cast(Root, obj).string_value) for obj in pool.objects},
            {(100, 'foo'), (101, 'bar')})
