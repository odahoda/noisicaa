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

import logging
from typing import cast, Any, Dict, Iterator, Callable

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model_base
from noisicaa import music
from noisicaa import node_db
from noisicaa.ui import object_list_editor
from noisicaa.ui import ui_base
from noisicaa.ui.graph import generic_node
from . import model

logger = logging.getLogger(__name__)


class NameColumnSpec(
        ui_base.ProjectMixin, object_list_editor.StringColumnSpec[model.CustomCSoundPort]):
    def header(self) -> str:
        return "ID"

    def value(self, obj: model.CustomCSoundPort) -> str:
        return obj.name

    def setValue(self, obj: model.CustomCSoundPort, value: str) -> None:
        for port in obj.node.ports:
            if port is obj:
                continue
            if value == port.name:
                # TODO: This should be communicated more clearly to the user.
                logger.warning("Refusing to use duplicate name '%s'", value)
                return

        with self.project.apply_mutations('%s: Change port name' % obj.node.name):
            if obj.csound_name == obj.csound_name_default():
                csound_name = obj.csound_name_default(name=value)
                if csound_name != obj.csound_name:
                    obj.csound_name = csound_name

            obj.name = value

    def addChangeListeners(
            self, obj: model.CustomCSoundPort, callback: Callable[[], None]
    ) -> Iterator[core.Listener]:
        yield obj.name_changed.add(lambda _: callback())

    def createEditor(
            self,
            obj: model.CustomCSoundPort,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        editor = super().createEditor(obj, delegate, parent, option, index)
        assert isinstance(editor, QtWidgets.QLineEdit)

        editor.setValidator(QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r'[a-zA-Z][-_:a-zA-Z0-9]{0,32}')))

        return editor


class DisplayNameColumnSpec(
        ui_base.ProjectMixin, object_list_editor.StringColumnSpec[model.CustomCSoundPort]):
    def header(self) -> str:
        return "Name"

    def value(self, obj: model.CustomCSoundPort) -> str:
        return obj.display_name

    def setValue(self, obj: model.CustomCSoundPort, value: str) -> None:
        with self.project.apply_mutations('%s: Change port display name' % obj.node.name):
            obj.display_name = value

    def addChangeListeners(
            self, obj: model.CustomCSoundPort, callback: Callable[[], None]
    ) -> Iterator[core.Listener]:
        yield obj.display_name_changed.add(lambda _: callback())


class TypeColumnSpec(
        ui_base.ProjectMixin, object_list_editor.ColumnSpec[model.CustomCSoundPort, int]):
    def header(self) -> str:
        return "Type"

    def value(self, obj: model.CustomCSoundPort) -> int:
        return obj.type

    def setValue(self, obj: model.CustomCSoundPort, value: int) -> None:
        with self.project.apply_mutations('%s: Change port type' % obj.node.name):
            if obj.csound_name == obj.csound_name_default():
                csound_name = obj.csound_name_default(
                    type=cast(node_db.PortDescription.Type, value))
                if csound_name != obj.csound_name:
                    obj.csound_name = csound_name

            obj.type = cast(node_db.PortDescription.Type, value)

    def addChangeListeners(
            self, obj: model.CustomCSoundPort, callback: Callable[[], None]
    ) -> Iterator[core.Listener]:
        yield obj.type_changed.add(lambda _: callback())

    def display(self, value: int) -> str:
        return {
            node_db.PortDescription.AUDIO: "audio",
            node_db.PortDescription.KRATE_CONTROL: "control (k-rate)",
            node_db.PortDescription.ARATE_CONTROL: "control (a-rate)",
            node_db.PortDescription.EVENTS: "events",
        }[cast(node_db.PortDescription.Type, value)]

    def createEditor(
            self,
            obj: model.CustomCSoundPort,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        current_port_type = self.value(obj)
        editor = QtWidgets.QComboBox(parent)
        editor.activated.connect(lambda: delegate.commitData.emit(editor))
        for name, port_type in [
                ("audio", node_db.PortDescription.AUDIO),
                ("control (k-rate)", node_db.PortDescription.KRATE_CONTROL),
                ("control (a-rate)", node_db.PortDescription.ARATE_CONTROL),
                ("events", node_db.PortDescription.EVENTS)]:
            editor.addItem(name, port_type)
            if port_type == current_port_type:
                editor.setCurrentIndex(editor.count() - 1)

        return editor

    def updateEditor(self, obj: model.CustomCSoundPort, editor: QtWidgets.QWidget) -> None:
        assert isinstance(editor, QtWidgets.QComboBox)
        port_type = self.value(obj)
        for idx in range(editor.count()):
            if editor.itemData(idx) == port_type:
                editor.setCurrentIndex(idx)
                break

    def editorValue(self, obj: model.CustomCSoundPort, editor: QtWidgets.QWidget) -> int:
        assert isinstance(editor, QtWidgets.QComboBox)
        return editor.currentData()


class DirectionColumnSpec(
        ui_base.ProjectMixin, object_list_editor.ColumnSpec[model.CustomCSoundPort, int]):
    def header(self) -> str:
        return "Direction"

    def value(self, obj: model.CustomCSoundPort) -> int:
        return obj.direction

    def setValue(self, obj: model.CustomCSoundPort, value: int) -> None:
        with self.project.apply_mutations('%s: Change port direction' % obj.node.name):
            obj.direction = cast(node_db.PortDescription.Direction, value)

    def addChangeListeners(
            self, obj: model.CustomCSoundPort, callback: Callable[[], None]
    ) -> Iterator[core.Listener]:
        yield obj.direction_changed.add(lambda _: callback())

    def display(self, value: int) -> str:
        return {
            node_db.PortDescription.INPUT: "input",
            node_db.PortDescription.OUTPUT: "output",
        }[cast(node_db.PortDescription.Direction, value)]

    def createEditor(
            self,
            obj: model.CustomCSoundPort,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        current_direction = self.value(obj)
        editor = QtWidgets.QComboBox(parent)
        editor.activated.connect(lambda: delegate.commitData.emit(editor))
        for name, direction in [
                ('input', node_db.PortDescription.INPUT),
                ('output', node_db.PortDescription.OUTPUT)]:
            editor.addItem(name, direction)
            if direction == current_direction:
                editor.setCurrentIndex(editor.count() - 1)

        return editor

    def updateEditor(self, obj: model.CustomCSoundPort, editor: QtWidgets.QWidget) -> None:
        assert isinstance(editor, QtWidgets.QComboBox)
        direction = self.value(obj)
        for idx in range(editor.count()):
            if editor.itemData(idx) == direction:
                editor.setCurrentIndex(idx)
                break

    def editorValue(self, obj: model.CustomCSoundPort, editor: QtWidgets.QWidget) -> int:
        assert isinstance(editor, QtWidgets.QComboBox)
        return editor.currentData()


class CSoundNameColumnSpec(
        ui_base.ProjectMixin, object_list_editor.StringColumnSpec[model.CustomCSoundPort]):
    def header(self) -> str:
        return "Variable"

    def value(self, obj: model.CustomCSoundPort) -> str:
        return obj.csound_name

    def setValue(self, obj: model.CustomCSoundPort, value: str) -> None:
        with self.project.apply_mutations('%s: Change port variable' % obj.node.name):
            obj.csound_name = value

    def addChangeListeners(
            self, obj: model.CustomCSoundPort, callback: Callable[[], None]
    ) -> Iterator[core.Listener]:
        yield obj.csound_name_changed.add(lambda _: callback())

    def createEditor(
            self,
            obj: model.CustomCSoundPort,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        editor = super().createEditor(obj, delegate, parent, option, index)
        assert isinstance(editor, QtWidgets.QLineEdit)

        if obj.type == node_db.PortDescription.EVENTS:
            regex = r'[0-9]+'
        else:
            regex = obj.csound_name_prefix() + r'[a-zA-Z0-9_]{1,30}'
        editor.setValidator(QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(regex)))

        return editor


class PortListEditor(ui_base.ProjectMixin, object_list_editor.ObjectListEditor):
    def __init__(self, *, node: model.CustomCSound, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setColumns(
            NameColumnSpec(context=self.context),
            CSoundNameColumnSpec(context=self.context),
            DisplayNameColumnSpec(context=self.context),
            TypeColumnSpec(context=self.context),
            DirectionColumnSpec(context=self.context),
        )

        self.__node = node

        for row, port in enumerate(self.__node.ports):
            self.objectAdded(port, row)

        self.__ports_listener = self.__node.ports_changed.add(self.__portsChanged)

    def __portsChanged(
            self, change: model_base.PropertyListChange[model.CustomCSoundPort]) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.objectAdded(change.new_value, change.index)

        elif isinstance(change, model_base.PropertyListDelete):
            self.objectRemoved(change.index)

        else:
            raise ValueError(type(change))

    def onAdd(self) -> None:
        num = 1
        while True:
            port_name = 'port%d' % num
            if all(port.name != port_name for port in self.__node.ports):
                break
            num += 1

        selected_rows = self.selectedRows()
        if selected_rows:
            index = max(selected_rows) + 1
        else:
            index = len(self.__node.ports)

        with self.project.apply_mutations('%s: Add port' % self.__node.name):
            port = self.__node.create_port(index, port_name)
        self.rowAdded(port.index)

    def onRemove(self) -> None:
        with self.project.apply_mutations('%s: Delete port(s)' % self.__node.name):
            for port in self.selectedObjects():
                assert isinstance(port, model.CustomCSoundPort)
                self.__node.delete_port(port)


class Editor(ui_base.ProjectMixin, QtWidgets.QDialog):
    def __init__(self, node: model.CustomCSound, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.__orchestra = self.__node.orchestra
        self.__score = self.__node.score

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowTitle("CSound Editor")

        icon_size = QtCore.QSize(32, 32)

        self.__apply_action = QtWidgets.QAction("Apply", self)
        self.__apply_action.setIcon(QtGui.QIcon.fromTheme('document-save'))
        self.__apply_action.setEnabled(False)
        self.__apply_action.triggered.connect(self.__apply)

        self.__apply_button = QtWidgets.QToolButton()
        self.__apply_button.setAutoRaise(True)
        self.__apply_button.setIconSize(icon_size)
        self.__apply_button.setDefaultAction(self.__apply_action)

        self.__orchestra_editor = QtWidgets.QTextEdit()
        self.__orchestra_editor.setPlainText(self.__orchestra)
        self.__orchestra_editor.textChanged.connect(self.__scriptEdited)
        self.__listeners['orchestra'] = self.__node.orchestra_changed.add(self.__orchestraChanged)

        self.__score_editor = QtWidgets.QTextEdit()
        self.__score_editor.setPlainText(self.__score)
        self.__score_editor.textChanged.connect(self.__scriptEdited)
        self.__listeners['score'] = self.__node.score_changed.add(self.__scoreChanged)

        self.__log = QtWidgets.QTextEdit()
        self.__log.setReadOnly(True)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__orchestra_editor, 2)
        l1.addWidget(self.__score_editor, 1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addLayout(l1)
        l2.addWidget(self.__log)

        l3 = QtWidgets.QHBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__apply_button)
        l3.addStretch(1)

        l4 = QtWidgets.QVBoxLayout()
        l4.setContentsMargins(0, 0, 0, 0)
        l4.addLayout(l3)
        l4.addLayout(l2)

        code_tab = QtWidgets.QWidget()
        code_tab.setLayout(l4)

        ports_tab = PortListEditor(node=self.__node, context=self.context)

        self.__tabs = QtWidgets.QTabWidget(self)
        self.__tabs.addTab(code_tab, "Code")
        self.__tabs.addTab(ports_tab, "Ports")

        l5 = QtWidgets.QVBoxLayout()
        l5.setContentsMargins(0, 0, 0, 0)
        l5.addWidget(self.__tabs)
        self.setLayout(l5)

    def __apply(self) -> None:
        self.__orchestra = self.__orchestra_editor.toPlainText()
        self.__score = self.__score_editor.toPlainText()

        with self.project.apply_mutations('%s: Change code' % self.__node.name):
            self.__node.orchestra = self.__orchestra
            self.__node.score = self.__score
        self.__apply_action.setEnabled(False)

    def __scriptEdited(self) -> None:
        self.__apply_action.setEnabled(
            self.__orchestra_editor.toPlainText() != self.__node.orchestra
            or self.__score_editor.toPlainText() != self.__node.score)

    def __orchestraChanged(self, change: model_base.PropertyValueChange[str]) -> None:
        if change.new_value != self.__orchestra:
            logger.error("oops")

    def __scoreChanged(self, change: model_base.PropertyValueChange[str]) -> None:
        if change.new_value != self.__score:
            logger.error("oops")

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        log = 'http://noisicaa.odahoda.de/lv2/processor_custom_csound#csound-log'
        if log in msg:
            self.__log.moveCursor(QtGui.QTextCursor.End)
            self.__log.insertPlainText(msg[log] + '\n')


class CustomCSoundNode(generic_node.GenericNode):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        super().__init__(node=node, **kwargs)

        assert isinstance(node, model.CustomCSound), type(node).__name__
        self.__node = node  # type: model.CustomCSound

        self.__editor = None  # type: Editor

    def cleanup(self) -> None:
        if self.__editor is not None:
            self.__editor.close()
            self.__editor = None

        super().cleanup()

    def buildContextMenu(self, menu: QtWidgets.QMenu) -> None:
        show_editor = menu.addAction("CSound Editor")
        show_editor.triggered.connect(self.__showEditor)

        super().buildContextMenu(menu)

    def __showEditor(self) -> None:
        if self.__editor is None:
            self.__editor = Editor(
                node=self.__node, parent=self.editor_window, context=self.context)

        self.__editor.show()
        self.__editor.raise_()
        self.__editor.activateWindow()
