#!/usr/bin/python3

import unittest
import json

from .state import (
    StateBase,
    StateMeta,
    Property,
    ListProperty,
    DictProperty,
    ObjectProperty,
    ObjectListProperty,
    ObjectReferenceProperty,
)


class PropertyTest(unittest.TestCase):
    def setUp(self):
        class TestObj(object):
            # pylint: disable=unused-argument
            def get_change_listeners(self, prop_name):
                return []

        self.obj = TestObj()
        self.obj.state = {}

    def testSet(self):
        p = Property(int)
        p.name = 'a'
        p.__set__(self.obj, 2)
        self.assertEqual(self.obj.state['a'], 2)

    def testGet(self):
        self.obj.state['a'] = 2
        p = Property(int)
        p.name = 'a'
        self.assertEqual(p.__get__(self.obj, self.obj.__class__), 2)

    def testGetDefault(self):
        p = Property(int, default=3)
        p.name = 'a'
        self.assertEqual(p.__get__(self.obj, self.obj.__class__), 3)

    def testSetBadType(self):
        p = Property(int)
        p.name = 'a'
        with self.assertRaises(TypeError):
            p.__set__(self.obj, 'foo')

    def testSetNotNone(self):
        p = Property(int)
        p.name = 'a'
        with self.assertRaises(ValueError):
            p.__set__(self.obj, None)

    def testSetNoneAllowed(self):
        p = Property(int, allow_none=True)
        p.name = 'a'
        p.__set__(self.obj, None)
        self.assertIsNone(self.obj.state['a'])

    def testList(self):
        p = ListProperty(int)
        p.name = 'a'
        l = p.__get__(self.obj, self.obj.__class__)
        self.assertEqual(l, [])
        l.extend([1, 2, 3])
        self.assertEqual(self.obj.state['a'], [1, 2, 3])

    def testListBadType(self):
        p = ListProperty(int)
        p.name = 'a'
        l = p.__get__(self.obj, self.obj.__class__)
        with self.assertRaises(TypeError):
            l.append("foo")

    def testListAccessor(self):
        p = ListProperty(int)
        p.name = 'a'
        l = p.__get__(self.obj, self.obj.__class__)
        l.extend([1, 2, 3])
        self.assertEqual(l, [1, 2, 3])
        self.assertEqual(l[0], 1)
        self.assertEqual(l[-1], 3)
        l[1] = 4
        self.assertEqual(p.__get__(self.obj, self.obj.__class__), [1, 4, 3])
        with self.assertRaises(TypeError):
            l[0] = "str"

    def testDict(self):
        p = DictProperty()
        p.name = 'a'
        self.assertEqual(p.__get__(self.obj, self.obj.__class__), {})
        d = p.__get__(self.obj, self.obj.__class__)
        d['foo'] = 1
        self.assertEqual(p.__get__(self.obj, self.obj.__class__), {'foo': 1})


class StateBaseTest(unittest.TestCase):
    def testMeta(self):
        self.assertIs(type(StateBase), StateMeta)


class LeafNode(StateBase):
    name = Property(str, default='')
    a1 = Property(int, default=2)

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)

class LeafNodeSub1(LeafNode):
    a2 = Property(int, default=7)
LeafNode.register_subclass(LeafNodeSub1)

class LeafNodeSub2(LeafNode):
    a3 = Property(int, default=9)
LeafNode.register_subclass(LeafNodeSub2)

class LeafNodeWithRef(LeafNode):
    other = ObjectReferenceProperty()

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)
LeafNode.register_subclass(LeafNodeWithRef)

class NodeWithChild(StateBase):
    child = ObjectProperty(cls=LeafNode)

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)

class NodeWithSubclassChild(StateBase):
    child = ObjectProperty(LeafNode)

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)

class NodeWithChildren(StateBase):
    children = ObjectListProperty(LeafNode)

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)


class StateTest(unittest.TestCase):
    def validateNode(self, root, parent, node):
        self.assertIs(node.parent, parent)
        self.assertIs(node.root, root)

        for c in node.list_children():
            self.validateNode(root, node, c)

    def validateTree(self, root):
        self.validateNode(root, None, root)

    def testListChildren(self):
        a = LeafNode()
        a.name = 'a'
        self.assertEqual(list(a.list_children()), [])
        b = NodeWithChild()
        b.child = a
        self.assertEqual(list(b.list_children()), [a])
        c = NodeWithChildren()
        c.children.append(b)
        self.assertEqual(list(c.list_children()), [b])

    def testSerialize(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'foo'
        self.validateTree(a)
        self.assertEqual(
            a.serialize(),
            {'__class__': 'LeafNode',
             'id': 'id1',
             'name': 'foo',
             'a1': 2})

    def testDeserialize(self):
        a = LeafNode(state={'name': 'foo'})
        self.validateTree(a)
        self.assertEqual(a.name, 'foo')
        self.assertEqual(a.a1, 2)

    def testAttr(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        self.validateTree(a)

        state = json.loads(json.dumps(a.serialize()))
        b = LeafNode(state=state)
        self.validateTree(b)
        self.assertEqual(b.id, 'id1')
        self.assertEqual(b.name, 'a')
        self.assertEqual(b.a1, 4)

    def testChildObject(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        b = NodeWithChild()
        b.id = 'id2'
        b.child = a
        self.validateTree(b)
        self.assertEqual(
            b.serialize(),
            {'__class__': 'NodeWithChild',
             'id': 'id2',
             'child': {'__class__': 'LeafNode',
                       'id': 'id1',
                       'name': 'a',
                       'a1': 4}})

        state = json.loads(json.dumps(b.serialize()))
        c = NodeWithChild(state=state)
        self.validateTree(c)
        self.assertEqual(c.id, 'id2')
        self.assertIsInstance(c.child, LeafNode)
        self.assertEqual(c.child.id, 'id1')
        self.assertEqual(c.child.name, 'a')
        self.assertEqual(c.child.a1, 4)

    def testInherit(self):
        a = LeafNodeSub1()
        a.id = 'id1'
        a.name = 'foo'
        a.a2 = 13
        self.validateTree(a)
        self.assertEqual(
            a.serialize(),
            {'__class__': 'LeafNodeSub1',
             'id': 'id1',
             'name': 'foo',
             'a1': 2,
             'a2': 13})

        state = json.loads(json.dumps(a.serialize()))
        b = LeafNodeSub1(state=state)
        self.validateTree(b)
        self.assertEqual(b.name, 'foo')
        self.assertEqual(b.a1, 2)
        self.assertEqual(b.a2, 13)

    def testChildObjectSubclass(self):
        a = LeafNodeSub2()
        a.id = 'id1'
        a.name = 'a'
        a.a3 = 17
        b = NodeWithSubclassChild()
        b.id = 'id2'
        b.child = a
        self.validateTree(b)
        self.assertEqual(
            b.serialize(),
            {'__class__': 'NodeWithSubclassChild',
             'id': 'id2',
             'child': {'__class__': 'LeafNodeSub2',
                       'id': 'id1',
                       'name': 'a',
                       'a1': 2,
                       'a3': 17}})

        state = json.loads(json.dumps(b.serialize()))
        c = NodeWithSubclassChild(state=state)
        self.validateTree(c)
        self.assertEqual(c.id, 'id2')
        self.assertIsInstance(c.child, LeafNodeSub2)
        self.assertEqual(c.child.id, 'id1')
        self.assertEqual(c.child.name, 'a')
        self.assertEqual(c.child.a1, 2)
        self.assertEqual(c.child.a3, 17)

    def testChildObjectList(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        b = LeafNode()
        b.id = 'id2'
        b.name = 'b'
        b.a1 = 5
        c = NodeWithChildren()
        c.id = 'id3'
        c.children.append(a)
        c.children.append(b)
        self.validateTree(c)
        self.assertEqual(
            c.serialize(),
            {'__class__': 'NodeWithChildren',
             'id': 'id3',
             'children': [{'__class__': 'LeafNode',
                           'id': 'id1',
                           'name': 'a',
                           'a1': 4},
                          {'__class__': 'LeafNode',
                           'id': 'id2',
                           'name': 'b',
                           'a1': 5}]})

        state = json.loads(json.dumps(c.serialize()))
        d = NodeWithChildren(state=state)
        self.validateTree(d)
        self.assertEqual(d.id, 'id3')
        self.assertIsInstance(d.children[0], LeafNode)
        self.assertEqual(d.children[0].id, 'id1')
        self.assertEqual(d.children[0].name, 'a')
        self.assertEqual(d.children[0].a1, 4)
        self.assertIsInstance(d.children[1], LeafNode)
        self.assertEqual(d.children[1].id, 'id2')
        self.assertEqual(d.children[1].name, 'b')
        self.assertEqual(d.children[1].a1, 5)

    def testObjectReference(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4
        b = LeafNodeWithRef()
        b.id = 'id2'
        b.name = 'b'
        b.a1 = 5
        b.other = a
        c = NodeWithChildren()
        c.id = 'id3'
        c.children.append(a)
        c.children.append(b)
        self.validateTree(c)
        self.assertEqual(
            c.serialize(),
            {'__class__': 'NodeWithChildren',
             'id': 'id3',
             'children': [{'__class__': 'LeafNode',
                           'id': 'id1',
                           'name': 'a',
                           'a1': 4},
                          {'__class__': 'LeafNodeWithRef',
                           'id': 'id2',
                           'name': 'b',
                           'a1': 5,
                           'other': 'ref:id1'}]})

        state = json.loads(json.dumps(c.serialize()))
        d = NodeWithChildren(state=state)
        d.init_references()
        self.validateTree(d)
        self.assertEqual(d.id, 'id3')
        self.assertIsInstance(d.children[0], LeafNode)
        self.assertEqual(d.children[0].id, 'id1')
        self.assertEqual(d.children[0].name, 'a')
        self.assertEqual(d.children[0].a1, 4)
        self.assertIsInstance(d.children[1], LeafNodeWithRef)
        self.assertEqual(d.children[1].id, 'id2')
        self.assertIs(d.children[1].other, d.children[0])

    def testChangeListener(self):
        a = LeafNode()
        a.id = 'id1'
        a.name = 'a'
        a.a1 = 4

        changes = []
        def listener(old_value, new_value):
            changes.append((old_value, new_value))
        a.add_change_listener('name', listener)
        a.name = 'b'
        a.name = 'b'
        a.name = 'c'
        self.assertEqual(changes, [('a', 'b'), ('b', 'c')])

    def testChangeListenerList(self):
        a = NodeWithChildren()

        n1 = LeafNode()
        n1.id = 'n1'
        n2 = LeafNode()
        n2.id = 'n2'
        n3 = LeafNode()
        n3.id = 'n3'
        n4 = LeafNode()
        n4.id = 'n4'

        changes = []
        def listener(action, *args):
            changes.append((action, args))
        a.add_change_listener('children', listener)
        a.children.append(n1)
        a.children.append(n2)
        a.children[1] = n3
        a.children.insert(1, n4)
        del a.children[0]
        a.children.clear()
        self.assertEqual(
            changes,
            [('insert', (0, n1)),
             ('insert', (1, n2)),
             ('delete', (1,)),
             ('insert', (1, n3)),
             ('insert', (1, n4)),
             ('delete', (0,)),
             ('clear', ()),
            ])


if __name__ == '__main__':
    unittest.main()
