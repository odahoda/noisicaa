#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import unittest
import json

from . import state
from noisicaa import core


# class PropertyTest(unittest.TestCase):
#     def setUp(self):
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

#     def testDict(self):
#         p = state.DictProperty()
#         p.name = 'a'
#         self.assertEqual(p.__get__(self.obj, self.obj.__class__), {})
#         d = p.__get__(self.obj, self.obj.__class__)
#         d['foo'] = 1
#         self.assertEqual(p.__get__(self.obj, self.obj.__class__), {'foo': 1})

class TestStateBase(state.StateBase):
    cls_map = {}


class StateTest(unittest.TestCase):
    def tearDown(self):
        TestStateBase.clear_class_registry()

    def validateNode(self, root, parent, node):
        self.assertIs(node.parent, parent)
        self.assertIs(node.root, root)

        for c in node.list_children():
            self.validateNode(root, node, c)

    def validateTree(self, root):
        self.validateNode(root, None, root)

    def testListChildrenLeaf(self):
        class Leaf(state.RootMixin, TestStateBase):
            pass
        a = Leaf()
        self.assertEqual(list(a.list_children()), [])

    def testListChildrenObjectProperty(self):
        class Leaf(TestStateBase):
            pass
        class Root(state.RootMixin, TestStateBase):
            child = core.ObjectProperty(Leaf)
        a = Leaf()
        b = Root()
        b.child = a

    def testListChildrenObjectListProperty(self):
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

    def testSerialize(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root()
        a.id = 'id1'
        a.name = 'foo'
        self.validateTree(a)
        self.assertEqual(
            a.serialize(),
            {'__class__': 'Root',
             'id': 'id1',
             'name': 'foo',
             'a1': 2})

    def testDeserialize(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root(state={'name': 'foo'})
        self.validateTree(a)
        self.assertEqual(a.name, 'foo')
        self.assertEqual(a.a1, 2)

    def testAttr(self):
        class Root(state.RootMixin, TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)

        a = Root()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        self.validateTree(a)

        serialized = json.loads(json.dumps(a.serialize()))
        b = Root(state=serialized)
        self.validateTree(b)
        self.assertEqual(b.id, 'id1')
        self.assertEqual(b.name, 'a')
        self.assertEqual(b.a1, 4)

    def testChildObject(self):
        class Leaf(TestStateBase):
            name = core.Property(str, default='')
            a1 = core.Property(int, default=2)
        TestStateBase.register_class(Leaf)

        class Root(state.RootMixin, TestStateBase):
            child = core.ObjectProperty(cls=Leaf)

        a = Leaf()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        b = Root()
        b.id = 'id2'
        b.child = a
        self.validateTree(b)
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
        self.validateTree(c)
        self.assertEqual(c.id, 'id2')
        self.assertIsInstance(c.child, Leaf)
        self.assertEqual(c.child.id, 'id1')
        self.assertEqual(c.child.name, 'a')
        self.assertEqual(c.child.a1, 4)

    # def testInherit(self):
    #     a = LeafNodeSub1()
    #     a.id = 'id1'
    #     a.name = 'foo'
    #     a.a2 = 13
    #     self.validateTree(a)
    #     self.assertEqual(
    #         a.serialize(),
    #         {'__class__': 'LeafNodeSub1',
    #          'id': 'id1',
    #          'name': 'foo',
    #          'a1': 2,
    #          'a2': 13})

    #     state = json.loads(json.dumps(a.serialize()))
    #     b = LeafNodeSub1(state=state)
    #     self.validateTree(b)
    #     self.assertEqual(b.name, 'foo')
    #     self.assertEqual(b.a1, 2)
    #     self.assertEqual(b.a2, 13)

    # def testChildObjectSubclass(self):
    #     a = LeafNodeSub2()
    #     a.id = 'id1'
    #     a.name = 'a'
    #     a.a3 = 17
    #     b = NodeWithSubclassChild()
    #     b.id = 'id2'
    #     b.child = a
    #     self.validateTree(b)
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
    #     self.validateTree(c)
    #     self.assertEqual(c.id, 'id2')
    #     self.assertIsInstance(c.child, LeafNodeSub2)
    #     self.assertEqual(c.child.id, 'id1')
    #     self.assertEqual(c.child.name, 'a')
    #     self.assertEqual(c.child.a1, 2)
    #     self.assertEqual(c.child.a3, 17)

    # def testChildObjectList(self):
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
    #     self.validateTree(c)
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
    #     self.validateTree(d)
    #     self.assertEqual(d.id, 'id3')
    #     self.assertIsInstance(d.children[0], LeafNode)
    #     self.assertEqual(d.children[0].id, 'id1')
    #     self.assertEqual(d.children[0].name, 'a')
    #     self.assertEqual(d.children[0].a1, 4)
    #     self.assertIsInstance(d.children[1], LeafNode)
    #     self.assertEqual(d.children[1].id, 'id2')
    #     self.assertEqual(d.children[1].name, 'b')
    #     self.assertEqual(d.children[1].a1, 5)

    def testObjectReference(self):
        class Leaf(TestStateBase):
            name = core.Property(str)
        TestStateBase.register_class(Leaf)

        class LeafWithRef(Leaf):
            other = core.ObjectReferenceProperty()
        TestStateBase.register_class(LeafWithRef)

        class Root(state.RootMixin, TestStateBase):
            children = core.ObjectListProperty(Leaf)

        a = Leaf()
        a.id = 'id1'
        a.name = 'a'
        b = LeafWithRef()
        b.id = 'id2'
        b.name = 'b'
        b.other = a
        c = Root()
        c.id = 'id3'
        c.children.append(a)
        c.children.append(b)
        self.validateTree(c)
        self.assertEqual(
            c.serialize(),
            {'__class__': 'Root',
             'id': 'id3',
             'children': [{'__class__': 'Leaf',
                           'id': 'id1',
                           'name': 'a'},
                          {'__class__': 'LeafWithRef',
                           'id': 'id2',
                           'name': 'b',
                           'other': 'ref:id1'}]})

        serialized = json.loads(json.dumps(c.serialize()))
        d = Root(state=serialized)
        d.init_references()
        self.validateTree(d)
        self.assertEqual(d.id, 'id3')
        self.assertIsInstance(d.children[0], Leaf)
        self.assertEqual(d.children[0].id, 'id1')
        self.assertEqual(d.children[0].name, 'a')
        self.assertIsInstance(d.children[1], LeafWithRef)
        self.assertEqual(d.children[1].id, 'id2')
        self.assertIs(d.children[1].other, d.children[0])

        # Remove child 1 with ref, serialize/deserialize and add it back.
        # Reference to child 0 must survive this.
        e = d.children[1]
        del d.children[1]
        e = LeafWithRef(state=json.loads(json.dumps(e.serialize())))
        d.children.append(e)
        self.assertIs(d.children[1].other, d.children[0])

    # def testChangeListener(self):
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

    # def testChangeListenerList(self):
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

    # def testObjectListIndex(self):
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

    # def testObjectListSiblings(self):
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


if __name__ == '__main__':
    unittest.main()
