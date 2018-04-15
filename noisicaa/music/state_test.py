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

# TODO: pylint-unclean

import json
from typing import Dict, Type  # pylint: disable=unused-import

from noisidev import unittest
from noisicaa import core
from . import state


# class PropertyTest(unittest.TestCase):
#     def setup_testcase(self):
#         class TestObj(state.StateBase):
#             pass

#         self.obj = TestObj()

#     def testSet(self):
#         p = core.Property(int)
#         p.name = 'a'
#         p.__set__(self.obj, 2)
#         self.assertEqual(self.obj.state['a'], 2)

#     def testGet(self):
#         self.obj.state['a'] = 2
#         p = state.Property(int)
#         p.name = 'a'
#         self.assertEqual(p.__get__(self.obj, self.obj.__class__), 2)

#     def testGetDefault(self):
#         p = state.Property(int, default=3)
#         p.name = 'a'
#         self.assertEqual(p.__get__(self.obj, self.obj.__class__), 3)

#     def testSetBadType(self):
#         p = state.Property(int)
#         p.name = 'a'
#         with self.assertRaises(TypeError):
#             p.__set__(self.obj, 'foo')

#     def testSetNotNone(self):
#         p = state.Property(int)
#         p.name = 'a'
#         with self.assertRaises(ValueError):
#             p.__set__(self.obj, None)

#     def testSetNoneAllowed(self):
#         p = state.Property(int, allow_none=True)
#         p.name = 'a'
#         p.__set__(self.obj, None)
#         self.assertIsNone(self.obj.state['a'])

#     def testList(self):
#         p = state.ListProperty(int)
#         p.name = 'a'
#         l = p.__get__(self.obj, self.obj.__class__)
#         self.assertEqual(l, [])
#         l.extend([1, 2, 3])
#         self.assertEqual(self.obj.state['a'], [1, 2, 3])

#     def testListBadType(self):
#         p = state.ListProperty(int)
#         p.name = 'a'
#         l = p.__get__(self.obj, self.obj.__class__)
#         with self.assertRaises(TypeError):
#             l.append("foo")

#     def testListAccessor(self):
#         p = state.ListProperty(int)
#         p.name = 'a'
#         l = p.__get__(self.obj, self.obj.__class__)
#         l.extend([1, 2, 3])
#         self.assertEqual(l, [1, 2, 3])
#         self.assertEqual(l[0], 1)
#         self.assertEqual(l[-1], 3)
#         l[1] = 4
#         self.assertEqual(p.__get__(self.obj, self.obj.__class__), [1, 4, 3])
#         with self.assertRaises(TypeError):
#             l[0] = "str"


class TestStateBase(state.StateBase):
    cls_map = {}  # type: Dict[str, Type[state.StateBase]]


class StateTest(unittest.TestCase):
    def cleanup_testcase(self):
        TestStateBase.clear_class_registry()

    def _validate_node(self, root, parent, node):
        self.assertIs(node.parent, parent)
        self.assertIs(node.root, root)

        for c in node.list_children():
            self._validate_node(root, node, c)

    def _validate_tree(self, root):
        self._validate_node(root, None, root)

    def test_list_children_leaf(self):
        class Leaf(state.RootMixin, TestStateBase):
            pass
        a = Leaf()
        self.assertEqual(list(a.list_children()), [])

    def test_list_children_object_property(self):
        class Leaf(TestStateBase):
            pass
        class Root(state.RootMixin, TestStateBase):
            child = core.ObjectProperty(Leaf)
        a = Leaf()
        b = Root()
        b.child = a

    def test_list_children_object_list_property(self):
        class Leaf(state.StateBase):
            pass
        class Root(state.RootMixin, TestStateBase):
            children = core.ObjectListProperty(Leaf)
        a = Leaf()
        b = Leaf()
        c = Root()
        c.children.append(a)
        c.children.append(b)
        self.assertEqual(list(c.list_children()), [a, b])

    def test_serialize(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root()
        a.id = 'id1'
        a.name = 'foo'
        self._validate_tree(a)
        self.assertEqual(
            a.serialize(),
            {'__class__': 'Root',
             'id': 'id1',
             'name': 'foo',
             'a1': 2})

    def test_deserialize(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root(state={'name': 'foo'})
        self._validate_tree(a)
        self.assertEqual(a.name, 'foo')
        self.assertEqual(a.a1, 2)

    def test_attr(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        self._validate_tree(a)

        serialized = json.loads(json.dumps(a.serialize()))
        b = Root(state=serialized)
        self._validate_tree(b)
        self.assertEqual(b.id, 'id1')
        self.assertEqual(b.name, 'a')
        self.assertEqual(b.a1, 4)

    def test_child_object(self):
        class Leaf(TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)
        TestStateBase.register_class(Leaf)

        class Root(state.RootMixin, TestStateBase):
            child = core.ObjectProperty(Leaf)

        a = Leaf()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        b = Root()
        b.id = 'id2'
        b.child = a
        self._validate_tree(b)
        self.assertEqual(
            b.serialize(),
            {'__class__': 'Root',
             'id': 'id2',
             'child': {'__class__': 'Leaf',
                       'id': 'id1',
                       'name': 'a',
                       'a1': 4}})

        serialized = json.loads(json.dumps(b.serialize()))
        c = Root(state=serialized)
        self._validate_tree(c)
        self.assertEqual(c.id, 'id2')
        self.assertIsInstance(c.child, Leaf)
        self.assertEqual(c.child.id, 'id1')
        self.assertEqual(c.child.name, 'a')
        self.assertEqual(c.child.a1, 4)

    # def test_inherit(self):
    #     a = LeafNodeSub1()
    #     a.id = 'id1'
    #     a.name = 'foo'
    #     a.a2 = 13
    #     self._validate_tree(a)
    #     self.assertEqual(
    #         a.serialize(),
    #         {'__class__': 'LeafNodeSub1',
    #          'id': 'id1',
    #          'name': 'foo',
    #          'a1': 2,
    #          'a2': 13})

    #     state = json.loads(json.dumps(a.serialize()))
    #     b = LeafNodeSub1(state=state)
    #     self._validate_tree(b)
    #     self.assertEqual(b.name, 'foo')
    #     self.assertEqual(b.a1, 2)
    #     self.assertEqual(b.a2, 13)

    # def test_child_object_subclass(self):
    #     a = LeafNodeSub2()
    #     a.id = 'id1'
    #     a.name = 'a'
    #     a.a3 = 17
    #     b = NodeWithSubclassChild()
    #     b.id = 'id2'
    #     b.child = a
    #     self._validate_tree(b)
    #     self.assertEqual(
    #         b.serialize(),
    #         {'__class__': 'NodeWithSubclassChild',
    #          'id': 'id2',
    #          'child': {'__class__': 'LeafNodeSub2',
    #                    'id': 'id1',
    #                    'name': 'a',
    #                    'a1': 2,
    #                    'a3': 17}})

    #     state = json.loads(json.dumps(b.serialize()))
    #     c = NodeWithSubclassChild(state=state)
    #     self._validate_tree(c)
    #     self.assertEqual(c.id, 'id2')
    #     self.assertIsInstance(c.child, LeafNodeSub2)
    #     self.assertEqual(c.child.id, 'id1')
    #     self.assertEqual(c.child.name, 'a')
    #     self.assertEqual(c.child.a1, 2)
    #     self.assertEqual(c.child.a3, 17)

    # def test_child_object_list(self):
    #     a = LeafNode()
    #     a.id = 'id1'
    #     a.name = 'a'
    #     a.a1 = 4
    #     b = LeafNode()
    #     b.id = 'id2'
    #     b.name = 'b'
    #     b.a1 = 5
    #     c = NodeWithChildren()
    #     c.id = 'id3'
    #     c.children.append(a)
    #     c.children.append(b)
    #     self._validate_tree(c)
    #     self.assertEqual(
    #         c.serialize(),
    #         {'__class__': 'NodeWithChildren',
    #          'id': 'id3',
    #          'children': [{'__class__': 'LeafNode',
    #                        'id': 'id1',
    #                        'name': 'a',
    #                        'a1': 4},
    #                       {'__class__': 'LeafNode',
    #                        'id': 'id2',
    #                        'name': 'b',
    #                        'a1': 5}]})

    #     state = json.loads(json.dumps(c.serialize()))
    #     d = NodeWithChildren(state=state)
    #     self._validate_tree(d)
    #     self.assertEqual(d.id, 'id3')
    #     self.assertIsInstance(d.children[0], LeafNode)
    #     self.assertEqual(d.children[0].id, 'id1')
    #     self.assertEqual(d.children[0].name, 'a')
    #     self.assertEqual(d.children[0].a1, 4)
    #     self.assertIsInstance(d.children[1], LeafNode)
    #     self.assertEqual(d.children[1].id, 'id2')
    #     self.assertEqual(d.children[1].name, 'b')
    #     self.assertEqual(d.children[1].a1, 5)

    # def test_change_listener(self):
    #     a = LeafNode()
    #     a.id = 'id1'
    #     a.name = 'a'
    #     a.a1 = 4

    #     changes = []
    #     def listener(old_value, new_value):
    #         changes.append((old_value, new_value))
    #     a.listeners.add('name', listener)
    #     a.name = 'b'
    #     a.name = 'b'
    #     a.name = 'c'
    #     self.assertEqual(changes, [('a', 'b'), ('b', 'c')])

    # def test_change_listener_list(self):
    #     a = NodeWithChildren()

    #     n1 = LeafNode()
    #     n1.id = 'n1'
    #     n2 = LeafNode()
    #     n2.id = 'n2'
    #     n3 = LeafNode()
    #     n3.id = 'n3'
    #     n4 = LeafNode()
    #     n4.id = 'n4'

    #     changes = []
    #     def listener(action, *args):
    #         changes.append((action, args))
    #     a.listeners.add('children', listener)
    #     a.children.append(n1)
    #     a.children.append(n2)
    #     a.children[1] = n3
    #     a.children.insert(1, n4)
    #     del a.children[0]
    #     a.children.clear()
    #     self.assertEqual(
    #         changes,
    #         [('insert', (0, n1)),
    #          ('insert', (1, n2)),
    #          ('delete', (1,)),
    #          ('insert', (1, n3)),
    #          ('insert', (1, n4)),
    #          ('delete', (0,)),
    #          ('clear', ()),
    #         ])

    # def test_object_list_index(self):
    #     a = LeafNode()
    #     with self.assertRaises(ObjectNotAttachedError):
    #         a.index

    #     b = LeafNode()

    #     c = NodeWithChildren()
    #     c.children.append(a)
    #     self.assertEqual(a.index, 0)

    #     c.children.append(b)
    #     self.assertEqual(b.index, 1)

    #     del c.children[0]
    #     with self.assertRaises(ObjectNotAttachedError):
    #         a.index
    #     self.assertEqual(b.index, 0)

    #     c.children.insert(0, a)
    #     self.assertEqual(a.index, 0)
    #     self.assertEqual(b.index, 1)

    # def test_object_list_siblings(self):
    #     l = NodeWithChildren()
    #     l.children.append(LeafNode())
    #     l.children.append(LeafNode())
    #     l.children.append(LeafNode())

    #     self.assertTrue(l.children[0].is_first)
    #     self.assertFalse(l.children[1].is_first)
    #     self.assertFalse(l.children[2].is_first)

    #     self.assertFalse(l.children[0].is_last)
    #     self.assertFalse(l.children[1].is_last)
    #     self.assertTrue(l.children[2].is_last)

    #     self.assertIs(l.children[0].next_sibling, l.children[1])
    #     self.assertIs(l.children[1].next_sibling, l.children[2])
    #     with self.assertRaises(IndexError):
    #         l.children[2].next_sibling

    #     with self.assertRaises(IndexError):
    #         l.children[0].prev_sibling
    #     self.assertIs(l.children[1].prev_sibling, l.children[0])
    #     self.assertIs(l.children[2].prev_sibling, l.children[1])

    def test_clone(self):
        class Child(state.StateBase):
            name = core.Property(str)

            def __init__(self, *, name=None, state=None):
                super().__init__(state=state)
                if state is None:
                    self.name = name

        class Object(state.RootMixin, state.StateBase):
            name = core.Property(str)
            lst = core.ListProperty(int)
            child = core.ObjectProperty(Child)
            none = core.ObjectProperty(Child)
            children = core.ObjectListProperty(Child)

            def __init__(self, *,
                         name=None, lst=None, child=None, children=None, state=None):
                super().__init__(state=state)
                if state is None:
                    self.name = name
                    self.lst.extend(lst)
                    self.child = child
                    self.none = None
                    self.children.extend(children)

        o2 = Object(
            name='bar',
            lst=[4, 5, 6],
            child=Child(name='c2'),
            children=[Child(name='cl3'), Child(name='cl4')],
        )

        o1 = o2.clone()

        self.assertNotEqual(o1.id, o2.id)
        self.assertEqual(o1.name, 'bar')
        self.assertEqual(o1.lst, [4, 5, 6])
        self.assertEqual(o1.child.name, 'c2')
        self.assertNotEqual(o1.child.id, o2.child.id)
        self.assertEqual(o1.children[0].name, 'cl3')
        self.assertNotEqual(o1.children[0].id, o2.children[0].id)
        self.assertEqual(o1.children[1].name, 'cl4')
        self.assertNotEqual(o1.children[1].id, o2.children[1].id)

    def test_copy_from(self):
        class Child(state.StateBase):
            name = core.Property(str)

            def __init__(self, *, name=None, state=None):
                super().__init__(state=state)
                if state is None:
                    self.name = name

        class Object(state.RootMixin, state.StateBase):
            name = core.Property(str)
            lst = core.ListProperty(int)
            child = core.ObjectProperty(Child)
            none = core.ObjectProperty(Child)
            children = core.ObjectListProperty(Child)

            def __init__(self, *,
                         name=None, lst=None, child=None, children=None, state=None):
                super().__init__(state=state)
                if state is None:
                    self.name = name
                    self.lst.extend(lst)
                    self.child = child
                    self.none = None
                    self.children.extend(children)

        o1 = Object(
            name='foo',
            lst=[1, 2, 3],
            child=Child(name='c1'),
            children=[Child(name='cl1'), Child(name='cl2')],
        )

        o2 = Object(
            name='bar',
            lst=[4, 5, 6],
            child=Child(name='c2'),
            children=[Child(name='cl3'), Child(name='cl4')],
        )

        id1 = o1.id
        o1.copy_from(o2)

        self.assertEqual(o1.id, id1)
        self.assertEqual(o1.name, 'bar')
        self.assertEqual(o1.lst, [4, 5, 6])
        self.assertEqual(o1.child.name, 'c2')
        self.assertNotEqual(o1.child.id, o2.child.id)
        self.assertEqual(o1.children[0].name, 'cl3')
        self.assertNotEqual(o1.children[0].id, o2.children[0].id)
        self.assertEqual(o1.children[1].name, 'cl4')
        self.assertNotEqual(o1.children[1].id, o2.children[1].id)
