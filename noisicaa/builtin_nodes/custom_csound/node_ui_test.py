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

from PySide2.QtCore import Qt
from PySide2 import QtWidgets

from noisidev import uitest
from noisicaa import node_db
from . import node_ui


class PortListEditorTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://custom-csound')

        with self.project.apply_mutations('test'):
            self.node.create_port(0, 'port1')
            self.node.create_port(1, 'port2')
            self.node.create_port(2, 'port3')

        self.port_list_editor = node_ui.PortListEditor(
            node=self.node, context=self.context)

        self.table = self.port_list_editor.findChild(
            QtWidgets.QTableView, "object_table", Qt.FindChildrenRecursively)
        self.model = self.table.model()
        self.delegate = self.table.itemDelegate()

    def _getCell(self, row, column):
        return self.model.data(self.model.index(row, column), Qt.DisplayRole)

    def _activeEditor(self):
        return self.port_list_editor.findChild(
            QtWidgets.QWidget, "attribute_editor", Qt.FindChildrenRecursively)

    def _closeEditor(self):
        editor = self._activeEditor()
        assert editor is not None
        self.delegate.commitData.emit(editor)
        self.delegate.closeEditor.emit(editor)
        editor.setParent(None)

    def _addAction(self):
        return self.port_list_editor.findChild(
            QtWidgets.QAction, "add_object", Qt.FindChildrenRecursively)

    def _removeAction(self):
        return self.port_list_editor.findChild(
            QtWidgets.QAction, "remove_objects", Qt.FindChildrenRecursively)

    async def test_port_added(self):
        with self.project.apply_mutations('test'):
            port = self.node.create_port(2, 'port4')
        self.assertIs(self.model.object(2), port)
        self.assertIs(self.model.object(3), self.node.ports[3])

    async def test_port_removed(self):
        with self.project.apply_mutations('test'):
            self.node.delete_port(self.node.ports[1])
        self.assertIs(self.model.object(0), self.node.ports[0])
        self.assertIs(self.model.object(1), self.node.ports[1])

    async def test_port_name_changed(self):
        with self.project.apply_mutations('test'):
            self.node.ports[0].name = 'foo'
        self.assertEqual(self._getCell(0, 0), 'foo')

    async def test_port_display_name_changed(self):
        with self.project.apply_mutations('test'):
            self.node.ports[0].display_name = 'Foo Bar'
        self.assertEqual(self._getCell(0, 2), 'Foo Bar')

    async def test_port_direction_changed(self):
        with self.project.apply_mutations('test'):
            self.node.ports[0].direction = node_db.PortDescription.OUTPUT
        self.assertEqual(self._getCell(0, 4), 'output')

    async def test_port_type_changed(self):
        with self.project.apply_mutations('test'):
            self.node.ports[0].type = node_db.PortDescription.KRATE_CONTROL
        self.assertEqual(self._getCell(0, 3), 'control (k-rate)')

    async def test_port_csound_name_changed(self):
        with self.project.apply_mutations('test'):
            self.node.ports[0].csound_name = 'gafoo'
        self.assertEqual(self._getCell(0, 1), 'gafoo')

    async def test_add_port(self):
        self._addAction().trigger()
        self.assertEqual(len(self.node.ports), 4)

    async def test_remove_ports(self):
        self.table.selectRow(1)

        self._removeAction().trigger()
        self.assertEqual(len(self.node.ports), 2)

    async def test_edit_name(self):
        self.table.edit(self.model.index(0, 0))
        editor = self._activeEditor()
        self.assertIsInstance(editor, QtWidgets.QLineEdit)
        editor.setText('foo')
        self._closeEditor()
        self.assertEqual(self.node.ports[0].name, 'foo')
        self.assertEqual(self.node.ports[0].csound_name, 'gaFoo')

    async def test_edit_display_name(self):
        self.table.edit(self.model.index(0, 2))
        editor = self._activeEditor()
        self.assertIsInstance(editor, QtWidgets.QLineEdit)
        editor.setText('Foo Bar')
        self._closeEditor()
        self.assertEqual(self.node.ports[0].display_name, 'Foo Bar')

    async def test_edit_direction(self):
        self.table.edit(self.model.index(0, 4))
        editor = self._activeEditor()
        self.assertIsInstance(editor, QtWidgets.QComboBox)
        editor.setCurrentIndex(0)
        self._closeEditor()
        self.assertEqual(self.node.ports[0].direction, node_db.PortDescription.INPUT)

    async def test_edit_type(self):
        tests = [
            (node_db.PortDescription.AUDIO, 'gaPort1',
             1, node_db.PortDescription.KRATE_CONTROL, 'gkPort1'),
            (node_db.PortDescription.AUDIO, 'gaPort1',
             2, node_db.PortDescription.ARATE_CONTROL, 'gaPort1'),
            (node_db.PortDescription.KRATE_CONTROL, 'gkPort1',
             0, node_db.PortDescription.AUDIO, 'gaPort1'),
            (node_db.PortDescription.EVENTS, '1',
             1, node_db.PortDescription.KRATE_CONTROL, 'gkPort1'),
        ]
        for initial_type, initial_csound_name, index, new_type, new_csound_name in tests:
            with self.subTest(
                    "%s -> %s" % (node_db.PortDescription.Type.Name(initial_type),
                                  node_db.PortDescription.Type.Name(new_type))):
                with self.project.apply_mutations('test'):
                    self.node.ports[0].type = initial_type
                    self.node.ports[0].csound_name = initial_csound_name

                self.table.edit(self.model.index(0, 3))
                editor = self._activeEditor()
                self.assertIsInstance(editor, QtWidgets.QComboBox)
                editor.setCurrentIndex(index)
                self._closeEditor()
                self.assertEqual(self.node.ports[0].type, new_type)
                self.assertEqual(self.node.ports[0].csound_name, new_csound_name)

    async def test_edit_csound_name(self):
        self.table.edit(self.model.index(0, 1))
        editor = self._activeEditor()
        self.assertIsInstance(editor, QtWidgets.QLineEdit)
        editor.setText('gaFoo')
        self._closeEditor()
        self.assertEqual(self.node.ports[0].csound_name, 'gaFoo')


class EditorTest(uitest.ProjectMixin, uitest.UITestCase):
    async def setup_testcase(self):
        with self.project.apply_mutations('test'):
            self.node = self.project.create_node('builtin://custom-csound')

    async def test_init(self):
        node_ui.Editor(node=self.node, context=self.context)
