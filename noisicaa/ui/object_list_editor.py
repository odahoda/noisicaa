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

import functools
import logging
from typing import Any, Dict, List, Set, Sequence, Iterator, Callable, Generic, TypeVar

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music

logger = logging.getLogger(__name__)


OBJECT = TypeVar('OBJECT', bound=music.ObjectBase)
VALUE = TypeVar('VALUE')


class ColumnSpec(Generic[OBJECT, VALUE]):
    def header(self) -> str:
        raise NotImplementedError

    def value(self, obj: OBJECT) -> VALUE:
        raise NotImplementedError

    def setValue(self, obj: OBJECT, value: VALUE) -> None:
        raise NotImplementedError

    def display(self, value: VALUE) -> str:
        raise NotImplementedError

    def addChangeListeners(
            self, obj: OBJECT, callback: Callable[[], None]) -> Iterator[core.Listener]:
        raise NotImplementedError

    def createEditor(
            self,
            obj: OBJECT,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        raise NotImplementedError

    def updateEditor(self, obj: OBJECT, editor: QtWidgets.QWidget) -> None:
        raise NotImplementedError

    def editorValue(self, obj: OBJECT, editor: QtWidgets.QWidget) -> VALUE:
        raise NotImplementedError


class StringColumnSpec(Generic[OBJECT], ColumnSpec[OBJECT, str]):
    def display(self, value: str) -> str:
        return value

    def createEditor(
            self,
            obj: OBJECT,
            delegate: QtWidgets.QAbstractItemDelegate,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        editor = QtWidgets.QLineEdit(parent)
        editor.setText(self.value(obj))
        return editor

    def updateEditor(self, obj: OBJECT, editor: QtWidgets.QWidget) -> None:
        assert isinstance(editor, QtWidgets.QLineEdit)
        editor.setText(self.value(obj))

    def editorValue(self, obj: OBJECT, editor: QtWidgets.QWidget) -> str:
        assert isinstance(editor, QtWidgets.QLineEdit)
        return editor.text()


class ObjectListModel(QtCore.QAbstractTableModel):
    def __init__(self, *, columns: List[ColumnSpec], **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__columns = columns
        self.__listeners = {}  # type: Dict[int, core.ListenerList]
        self.__objects = []  # type: List[music.ObjectBase]

    def cleanup(self) -> None:
        for listeners in self.__listeners.values():
            listeners.cleanup()
        self.__listeners.clear()

    def objectAdded(self, obj: music.ObjectBase, row: int) -> None:
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.__objects.insert(row, obj)
        self.endInsertRows()

        listeners = self.__listeners[obj.id] = core.ListenerList()
        for column, col_spec in enumerate(self.__columns):
            listeners.extend(col_spec.addChangeListeners(
                obj, functools.partial(self.__valueChanged, obj, column)))

    def objectRemoved(self, row: int) -> None:
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        obj = self.__objects.pop(row)
        self.endRemoveRows()

        self.__listeners.pop(obj.id).cleanup()

    def __valueChanged(self, obj: music.ObjectBase, column: int) -> None:
        for row, robj in enumerate(self.__objects):
            if robj.id == obj.id:
                self.dataChanged.emit(self.index(row, column), self.index(row, column))
                break

    def object(self, row: int) -> music.ObjectBase:
        return self.__objects[row]

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self.__columns)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self.__objects)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        flags |= Qt.ItemIsEditable
        return flags

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        col_spec = self.__columns[index.column()]
        obj = self.__objects[index.row()]

        if role == Qt.DisplayRole:
            return col_spec.display(col_spec.value(obj))

        elif role == Qt.EditRole:
            return col_spec.value(obj)

        return None

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole:
            return False

        if not index.isValid():
            return False

        col_spec = self.__columns[index.column()]
        obj = self.__objects[index.row()]
        if col_spec.value(obj) != value:
            col_spec.setValue(obj, value)

        return True

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.__columns[section].header()

        else:
            return "%d" % section


class ObjectListDelegate(QtWidgets.QItemDelegate):
    def __init__(self, *, columns: List[ColumnSpec], **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__columns = columns

    def createEditor(
            self,
            parent: QtWidgets.QWidget,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        col_spec = self.__columns[index.column()]
        obj = index.model().object(index.row())
        editor = col_spec.createEditor(obj, self, parent, option, index)
        editor.setObjectName('attribute_editor')
        return editor

    def setEditorData(self, editor: QtWidgets.QWidget, index: QtCore.QModelIndex) -> None:
        col_spec = self.__columns[index.column()]
        obj = index.model().object(index.row())
        col_spec.updateEditor(obj, editor)

    def setModelData(
            self,
            editor: QtWidgets.QWidget,
            model: QtCore.QAbstractItemModel,
            index: QtCore.QModelIndex
    ) -> None:
        col_spec = self.__columns[index.column()]
        obj = model.object(index.row())
        value = col_spec.editorValue(obj, editor)
        model.setData(index, value)


class ObjectListView(QtWidgets.QTableView):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName('object_table')
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.horizontalHeader().setVisible(True)
        self.verticalHeader().setVisible(False)

    def selectedRows(self) -> Set[int]:
        return {
            index.row() for index in self.selectedIndexes()
        }


class ObjectListEditor(core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__columns = None  # type: List[ColumnSpec]
        self.__model = None  # type: ObjectListModel
        self.__delegate = None  # type: ObjectListDelegate

        icon_size = QtCore.QSize(24, 24)

        self.__add_action = QtWidgets.QAction("Add", self)
        self.__add_action.setObjectName('add_object')
        self.__add_action.setIcon(QtGui.QIcon.fromTheme('list-add'))
        self.__add_action.triggered.connect(self.onAdd)

        self.__add_button = QtWidgets.QToolButton()
        self.__add_button.setAutoRaise(True)
        self.__add_button.setIconSize(icon_size)
        self.__add_button.setDefaultAction(self.__add_action)

        self.__remove_action = QtWidgets.QAction("Remove", self)
        self.__remove_action.setObjectName('remove_objects')
        self.__remove_action.setIcon(QtGui.QIcon.fromTheme('list-remove'))
        self.__remove_action.triggered.connect(self.onRemove)

        self.__remove_button = QtWidgets.QToolButton()
        self.__remove_button.setAutoRaise(True)
        self.__remove_button.setIconSize(icon_size)
        self.__remove_button.setDefaultAction(self.__remove_action)

        self.__list = ObjectListView()

        l7 = QtWidgets.QHBoxLayout()
        l7.setContentsMargins(0, 0, 0, 0)
        l7.addWidget(self.__add_button)
        l7.addWidget(self.__remove_button)
        l7.addStretch(1)

        l6 = QtWidgets.QVBoxLayout()
        l6.setContentsMargins(0, 0, 0, 0)
        l6.addLayout(l7)
        l6.addWidget(self.__list)

        self.setLayout(l6)

    def setColumns(self, *columns: ColumnSpec) -> None:
        assert self.__columns is None
        self.__columns = list(columns)
        self.__model = ObjectListModel(columns=self.__columns)
        self.add_cleanup_function(self.__model.cleanup)
        self.__delegate = ObjectListDelegate(columns=self.__columns)
        self.__list.setModel(self.__model)
        self.__list.setItemDelegate(self.__delegate)

    def objectAdded(self, obj: music.ObjectBase, row: int) -> None:
        self.__model.objectAdded(obj, row)

    def objectRemoved(self, row: int) -> None:
        self.__model.objectRemoved(row)

    def selectedRows(self) -> Set[int]:
        return self.__list.selectedRows()

    def selectedObjects(self) -> Sequence[music.ObjectBase]:
        return [
            self.__model.object(row) for row in self.__list.selectedRows()
        ]

    def rowAdded(self, row: int) -> None:
        self.__list.setCurrentIndex(self.__model.index(row, 0))
        self.__list.edit(self.__model.index(row, 0))

    def onAdd(self) -> None:
        raise NotImplementedError

    def onRemove(self) -> None:
        raise NotImplementedError
