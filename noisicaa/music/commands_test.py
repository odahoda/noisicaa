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

from noisidev import unittest
from noisicaa import core
from . import commands
from . import state


class ChangeName(commands.Command):
    new_name = core.Property(str)

    def __init__(self, new_name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.new_name = new_name

    def run(self, obj):
        self.set_property(obj, 'name', self.new_name)

commands.Command.register_command(ChangeName)


class AddChild(commands.Command):
    child_name = core.Property(str)

    def __init__(self, child_name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.child_name = child_name

    def run(self, obj):
        child = Child(name=self.child_name)
        self.list_insert(obj, 'children', len(obj.children), child)

commands.Command.register_command(AddChild)


class RemoveChild(commands.Command):
    child_index = core.Property(int)

    def __init__(self, child_index=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.child_index = child_index

    def run(self, obj):
        self.list_delete(obj, 'children', self.child_index)

commands.Command.register_command(RemoveChild)


class MoveChild(commands.Command):
    old_index = core.Property(int)
    new_index = core.Property(int)

    def __init__(self, old_index=None, new_index=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.old_index = old_index
            self.new_index = new_index

    def run(self, obj):
        self.list_move(obj, 'children', self.old_index, self.new_index)

commands.Command.register_command(MoveChild)


class Child(state.StateBase):
    name = core.Property(str)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

        self.commands = []


class Root(state.RootMixin, state.StateBase):
    name = core.Property(str)
    children = core.ObjectListProperty(Child)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

Root.register_class(Child)


class CommandTest(unittest.TestCase):
    def test_set_property(self):
        root = Root(name='old_name')
        root_serialized_pre = root.serialize()

        cmd = ChangeName(new_name='new_name')
        cmd.apply(root)
        self.assertEqual(root.name, 'new_name')
        root_serialized_post = root.serialize()

        cmd = commands.Command.create_from_state(cmd.serialize())

        cmd.undo(root)
        self.assertEqual(root.serialize(), root_serialized_pre)

        cmd.redo(root)
        self.assertEqual(root.serialize(), root_serialized_post)

    def test_list_insert(self):
        root = Root(name='root')
        root_serialized_pre = root.serialize()

        cmd = AddChild(child_name='added_child')
        cmd.apply(root)
        self.assertEqual(len(root.children), 1)
        self.assertEqual(root.children[0].name, 'added_child')
        root_serialized_post = root.serialize()

        cmd = commands.Command.create_from_state(cmd.serialize())

        cmd.undo(root)
        self.assertEqual(root.serialize(), root_serialized_pre)

        cmd.redo(root)
        self.assertEqual(root.serialize(), root_serialized_post)

    def test_list_delete(self):
        root = Root(name='root')
        root.children.insert(0, Child(name='removed_child'))
        root_serialized_pre = root.serialize()

        cmd = RemoveChild(child_index=0)
        cmd.apply(root)
        self.assertEqual(len(root.children), 0)
        root_serialized_post = root.serialize()

        cmd = commands.Command.create_from_state(cmd.serialize())

        cmd.undo(root)
        self.assertEqual(root.serialize(), root_serialized_pre)

        cmd.redo(root)
        self.assertEqual(root.serialize(), root_serialized_post)

    def test_list_move(self):
        root = Root(name='root')
        root.children.insert(0, Child(name='child1'))
        root.children.insert(1, Child(name='child2'))
        root_serialized_pre = root.serialize()

        cmd = MoveChild(old_index=1, new_index=0)
        cmd.apply(root)
        self.assertEqual(root.children[0].name, 'child2')
        self.assertEqual(root.children[1].name, 'child1')
        root_serialized_post = root.serialize()

        cmd = commands.Command.create_from_state(cmd.serialize())

        cmd.undo(root)
        self.assertEqual(root.serialize(), root_serialized_pre)

        cmd.redo(root)
        self.assertEqual(root.serialize(), root_serialized_post)
