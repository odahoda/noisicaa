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
from typing import List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import project_registry as project_registry_lib
from . import slots

logger = logging.getLogger(__name__)


class ProjectListItem(slots.SlotContainer, QtWidgets.QWidget):
    selected, setSelected, selectedChanged = slots.slot(bool, 'selected')

    def __init__(
            self,
            project: project_registry_lib.Project,
            dialog: 'OpenProjectDialog',
            parent: QtWidgets.QWidget = None
    ) -> None:
        super().__init__(parent=parent)

        self.__project = project
        self.__dialog = dialog
        self.__hovered = False

        self.setBackgroundRole(QtGui.QPalette.Base)
        self.setAutoFillBackground(True)

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

        self.selectedChanged.connect(lambda _: self.__updateBackgound())

    def project(self) -> project_registry_lib.Project:
        return self.__project

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        self.__hovered = True
        self.__updateBackgound()
        super().enterEvent(evt)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.__hovered = False
        self.__updateBackgound()
        super().leaveEvent(evt)

    def __updateBackgound(self) -> None:
        if self.selected():
            self.setBackgroundRole(QtGui.QPalette.Highlight)
        elif self.__hovered:
            self.setBackgroundRole(QtGui.QPalette.AlternateBase)
        else:
            self.setBackgroundRole(QtGui.QPalette.Base)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            if self.selected():
                self.__dialog.selectProject(None)
            else:
                self.__dialog.selectProject(self)
            return

        super().mousePressEvent(evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.__dialog.openProject(self)
            return

        super().mouseDoubleClickEvent(evt)


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

        self.__list = QtWidgets.QWidget(self)
        self.__list.setBackgroundRole(QtGui.QPalette.Base)
        self.__list_items = []  # type: List[ProjectListItem]
        self.__list_layout = QtWidgets.QVBoxLayout()
        self.__list_layout.setContentsMargins(4, 2, 4, 2)
        self.__list_layout.setSpacing(4)
        self.__list_layout.addStretch(1)
        self.__list.setLayout(self.__list_layout)
        self.__list_view = QtWidgets.QScrollArea(self)
        self.__list_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.__list_view.setWidgetResizable(True)
        self.__list_view.setWidget(self.__list)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__open_button)
        l1.addWidget(self.__more_button)
        l1.addStretch(1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__list_view)
        l2.addLayout(l1)

        l3 = QtWidgets.QVBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__search)
        l3.addLayout(l2)
        self.setLayout(l3)

        for project in self.__project_registry.projects:
            self.__addProject(project)

    def cleanup(self) -> None:
        pass

    def selectProject(self, item: ProjectListItem) -> None:
        if item is not None:
            self.__open_button.setDisabled(False)
            self.__more_button.setDisabled(False)
        else:
            self.__open_button.setDisabled(True)
            self.__more_button.setDisabled(True)

        for pitem in self.__list_items:
            if pitem is item:
                pitem.setSelected(True)
            else:
                pitem.setSelected(False)

    def openProject(self, item: ProjectListItem) -> None:
        self.projectSelected.emit(item.project())

    def __addProject(self, project: project_registry_lib.Project) -> None:
        item = ProjectListItem(project, self, self.__list)

        self.__list_items.append(item)

        if self.__list_layout.count() > 1:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setFrameShadow(QtWidgets.QFrame.Plain)
            self.__list_layout.insertWidget(self.__list_layout.count() - 1, sep)

        self.__list_layout.insertWidget(self.__list_layout.count() - 1, item)
