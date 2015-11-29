#!/usr/bin/python3

import unittest

from . import commands

class TestCommand(commands.Command):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self, obj):
        obj.commands.append(self.name)

class TestObject(commands.CommandDispatcher):
    def __init__(self):
        super().__init__()
        self.commands = []


class CommandDispatcherTest(unittest.TestCase):
    def setUp(self):
        self.leaf_a = TestObject()
        self.leaf_b = TestObject()
        self.leaf_c = TestObject()

        self.inner_a = TestObject()
        self.inner_a.add_sub_target('leaf_b', self.leaf_b)
        self.inner_a.add_sub_target('leaf_c', self.leaf_c)

        self.root = TestObject()
        self.root.set_root()
        self.root.add_sub_target('leaf_a', self.leaf_a)
        self.root.add_sub_target('inner_a', self.inner_a)

    def testTargetRoot(self):
        self.root.dispatch_command('/', TestCommand('cmd1'))
        self.assertEqual(self.root.commands, ['cmd1'])
        self.assertEqual(self.leaf_a.commands, [])

    def testTargetLeafA(self):
        self.root.dispatch_command('/leaf_a', TestCommand('cmd1'))
        self.assertEqual(self.leaf_a.commands, ['cmd1'])

    def testTargetLeafB(self):
        self.root.dispatch_command('/inner_a/leaf_b', TestCommand('cmd1'))
        self.assertEqual(self.leaf_b.commands, ['cmd1'])

    def testTargetInnerA(self):
        self.root.dispatch_command('/inner_a', TestCommand('cmd1'))
        self.assertEqual(self.inner_a.commands, ['cmd1'])


if __name__ == '__main__':
    unittest.main()
