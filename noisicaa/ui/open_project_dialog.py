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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import project_registry as project_registry_lib
from . import slots

logger = logging.getLogger(__name__)


class ProjectItem(slots.SlotContainer, QtWidgets.QWidget):
    def __init__(self, project: project_registry_lib.Project) -> None:
        super().__init__()

        self.__project = project

        name = QtWidgets.QLabel(self)
        name.setText(self.__project.name)
        name_font = QtGui.QFont(name.font())
        name_font.setPointSizeF(1.4 * name_font.pointSizeF())
        name_font.setBold(True)
        name.setFont(name_font)

        path = QtWidgets.QLabel(self)
        path.setText(self.__project.path)
        path_font = QtGui.QFont(path.font())
        path.setFont(path_font)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(name)
        l1.addWidget(path)
        self.setLayout(l1)


class ItemDelegate(QtWidgets.QAbstractItemDelegate):
    def __init__(self) -> None:
        super().__init__()

        self.__widgets = {}  # type: Dict[QtCore.QModelIndex, QtWidgets.QWidget]

    def __getWidget(self, index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        if index not in self.__widgets:
            item = index.model().item(index)
            if isinstance(item, project_registry_lib.Project):
                widget = ProjectItem(item)
                widget.setAutoFillBackground(True)
            else:
                raise TypeError(type(item))
            self.__widgets[index] = widget

        return self.__widgets[index]

    def paint(
            self,
            painter: QtGui.QPainter,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> None:
        widget = self.__getWidget(index)
        widget.resize(option.rect.size())
        if option.state & QtWidgets.QStyle.State_Selected:
            widget.setBackgroundRole(QtGui.QPalette.Highlight)
        else:
            widget.setBackgroundRole(QtGui.QPalette.Base)

        # Why do I have to render to a pixmap first? QWidget.render() should be able to directly
        # render into a QPainter...
        pixmap = QtGui.QPixmap(option.rect.size())
        widget.render(pixmap)
        painter.drawPixmap(option.rect, pixmap)

    def sizeHint(
            self,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> QtCore.QSize:
        widget = self.__getWidget(index)
        return widget.sizeHint()


class ProjectListView(QtWidgets.QListView):
    numProjectsSelected = QtCore.pyqtSignal(int)
    itemDoubleClicked = QtCore.pyqtSignal(project_registry_lib.Item)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.__delegate = ItemDelegate()
        self.setItemDelegate(self.__delegate)

        self.doubleClicked.connect(self.__doubleClicked)

    def __doubleClicked(self, index: QtCore.QModelIndex) -> None:
        self.itemDoubleClicked.emit(index.model().item(index))

    def selectionChanged(
            self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection) -> None:
        self.numProjectsSelected.emit(len(self.selectedIndexes()))


class FlatProjectListModel(QtCore.QAbstractListModel):
    def __init__(self, project_registry: project_registry_lib.ProjectRegistry) -> None:
        super().__init__()

        self.__registry = project_registry
        self.__root = QtCore.QModelIndex()

    def item(self, index: QtCore.QModelIndex = QtCore.QModelIndex()) -> project_registry_lib.Item:
        return self.__registry.item(
            self.__registry.index(index.row(), index.column(), self.__root))

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return self.__registry.rowCount(self.__root)

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        return self.__registry.data(
            self.__registry.index(index.row(), index.column(), self.__root),
            role)

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        return self.__registry.headerData(section, orientation, role)


class OpenProjectDialog(QtWidgets.QWidget):
    projectSelected = QtCore.pyqtSignal(project_registry_lib.Project)

    def __init__(
            self,
            parent: QtWidgets.QWidget = None,
            *,
            project_registry: project_registry_lib.ProjectRegistry
    ) -> None:
        super().__init__(parent)

        self.__project_registry = project_registry

        self.__search = QtWidgets.QLineEdit(self)

        self.__open_button = QtWidgets.QPushButton(self)
        self.__open_button.setText("Open")
        self.__open_button.setDisabled(True)

        self.__delete_action = QtWidgets.QAction("Delete", self)
        self.__archive_action = QtWidgets.QAction("Archive", self)

        self.__more_menu = QtWidgets.QMenu()
        self.__more_menu.addAction(self.__delete_action)
        self.__more_menu.addAction(self.__archive_action)

        self.__more_button = QtWidgets.QPushButton(self)
        self.__more_button.setText("More")
        self.__more_button.setMenu(self.__more_menu)
        self.__more_button.setDisabled(True)

        self.__list = ProjectListView(self)
        self.__list.setModel(FlatProjectListModel(self.__project_registry))
        self.__list.numProjectsSelected.connect(lambda count: self.__updateButtons(count == 1))
        self.__list.itemDoubleClicked.connect(self.openProject)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__open_button)
        l1.addWidget(self.__more_button)
        l1.addStretch(1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__list)
        l2.addLayout(l1)

        l3 = QtWidgets.QVBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__search)
        l3.addLayout(l2)
        self.setLayout(l3)

    def cleanup(self) -> None:
        pass

    def __updateButtons(self, enable: bool) -> None:
        self.__open_button.setDisabled(not enable)
        self.__more_button.setDisabled(not enable)

    def openProject(self, project: project_registry_lib.Project) -> None:
        self.projectSelected.emit(project)
