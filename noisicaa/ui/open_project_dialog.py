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

import datetime
import functools
import logging
import os.path
import random
import time
from typing import Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import humanize

from noisicaa import title_generator
from . import project_registry as project_registry_lib
from . import slots
from . import ui_base

logger = logging.getLogger(__name__)


class ProjectItem(slots.SlotContainer, QtWidgets.QWidget):
    def __init__(self, project: project_registry_lib.Project) -> None:
        super().__init__()

        self.__project = project

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

        mtime = QtWidgets.QLabel(self)
        mtime.setText('Last usage: %s' % humanize.naturaltime(datetime.datetime.fromtimestamp(self.__project.mtime)))

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(name)
        l1.addWidget(path)
        l1.addWidget(mtime)
        self.setLayout(l1)


class ItemDelegate(QtWidgets.QAbstractItemDelegate):
    def __init__(self) -> None:
        super().__init__()

        self.__widgets = {}  # type: Dict[QtCore.QModelIndex, QtWidgets.QWidget]

    def __getWidget(self, index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        item = index.model().item(index)
        if item.path not in self.__widgets:
            if isinstance(item, project_registry_lib.Project):
                widget = ProjectItem(item)
            else:
                raise TypeError(type(item))
            self.__widgets[item.path] = widget

        return self.__widgets[item.path]

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

        self.setSpacing(4)

        self.doubleClicked.connect(self.__doubleClicked)

    def __doubleClicked(self, index: QtCore.QModelIndex) -> None:
        item = self.model().item(index)
        self.itemDoubleClicked.emit(item)

    def selectionChanged(
            self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection) -> None:
        self.numProjectsSelected.emit(len(self.selectedIndexes()))

    def selectedProjects(self) -> List[project_registry_lib.Project]:
        projects = []
        for index in self.selectedIndexes():
            item = self.model().item(index)
            if isinstance(item, project_registry_lib.Project):
                projects.append(item)

        return projects


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


class FilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()

        self.__filter = []  # type: List[str]

    def item(self, index: QtCore.QModelIndex = QtCore.QModelIndex()) -> project_registry_lib.Item:
        source_model = self.sourceModel()
        return source_model.item(self.mapToSource(index))

    def setFilterWords(self, text: str) -> None:
        words = text.split()
        words = [word.strip() for word in words]
        words = [word for word in words if word]
        words = [word.lower() for word in words]
        self.__filter = words
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:
        if not self.__filter:
            return True

        model = self.sourceModel()
        parent_item = model.item(parent)
        item = parent_item.children[row]

        return all(word in item.name.lower() for word in self.__filter)


class NewProjectDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setWindowTitle("noisicaä - New Project")
        self.setMinimumWidth(500)

        self.__create_button = QtWidgets.QPushButton(self)
        self.__create_button.setIcon(QtGui.QIcon.fromTheme('document-new'))
        self.__create_button.setText("Create")
        self.__create_button.clicked.connect(self.accept)

        self.__close_button = QtWidgets.QPushButton(self)
        self.__close_button.setIcon(QtGui.QIcon.fromTheme('window-close'))
        self.__close_button.setText("Cancel")
        self.__close_button.clicked.connect(self.reject)

        self.__name = QtWidgets.QLineEdit(self)
        self.__name.textChanged.connect(self.__nameChanged)

        self.__error = QtWidgets.QLabel(self)
        palette = QtGui.QPalette(self.__error.palette())
        palette.setColor(QtGui.QPalette.WindowText, Qt.red)
        self.__error.setPalette(palette)

        self.__prev_name = QtWidgets.QToolButton(self)
        self.__prev_name.setIcon(QtGui.QIcon.fromTheme('go-previous'))
        self.__prev_name.clicked.connect(self.__prevNameClicked)

        self.__next_name = QtWidgets.QToolButton(self)
        self.__next_name.setIcon(QtGui.QIcon.fromTheme('go-next'))
        self.__next_name.clicked.connect(self.__nextNameClicked)

        self.__name_seed = random.randint(0, 1000000)
        self.__generateName()

        l4 = QtWidgets.QHBoxLayout()
        l4.addWidget(self.__name, 1)
        l4.addWidget(self.__prev_name)
        l4.addWidget(self.__next_name)

        l3 = QtWidgets.QFormLayout()
        l3.addRow("Name:", l4)

        l2 = QtWidgets.QHBoxLayout()
        l2.addStretch(1)
        l2.addWidget(self.__create_button)
        l2.addWidget(self.__close_button)

        l1 = QtWidgets.QVBoxLayout()
        l1.addLayout(l3)
        l1.addWidget(self.__error)
        l1.addLayout(l2)
        self.setLayout(l1)

    def projectDir(self) -> str:
        directory = '~/Music/Noisicaä'
        directory = os.path.expanduser(directory)
        directory = os.path.abspath(directory)
        return directory

    def projectName(self) -> str:
        return self.__name.text()

    def projectPath(self) -> str:
        filename = self.projectName() + '.noise'
        filename = filename.replace('%', '%25')
        filename = filename.replace('/', '%2F')
        return os.path.join(self.projectDir(), filename)

    def __generateName(self) -> None:
        gen = title_generator.TitleGenerator(self.__name_seed)
        self.__name.setText(gen.generate())

    def __nextNameClicked(self) -> None:
        self.__name_seed = (self.__name_seed + 1) % 1000000
        self.__generateName()

    def __prevNameClicked(self) -> None:
        self.__name_seed = (self.__name_seed - 1) % 1000000
        self.__generateName()

    def __nameChanged(self, text: str) -> None:
        self.__create_button.setEnabled(False)
        self.__error.setVisible(True)
        if not text:
            self.__error.setText("Enter a valid project name.")
        elif os.path.exists(self.projectPath()):
            self.__error.setText("A project of this name already exists.")
        else:
            self.__create_button.setEnabled(True)
            self.__error.setVisible(False)


class OpenProjectDialog(ui_base.CommonMixin, QtWidgets.QWidget):
    projectSelected = QtCore.pyqtSignal(project_registry_lib.Project)
    createProject = QtCore.pyqtSignal(str)

    def __init__(
            self, *,
            project_registry: project_registry_lib.ProjectRegistry,
            **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.__project_registry = project_registry

        self.__search = QtWidgets.QLineEdit(self)
        search_action = QtWidgets.QAction(self.__search)
        search_action.setIcon(QtGui.QIcon.fromTheme('edit-find'))
        self.__search.addAction(search_action, QtWidgets.QLineEdit.LeadingPosition)
        clear_action = QtWidgets.QAction("Clear search string", self.__search)
        clear_action.setIcon(QtGui.QIcon.fromTheme('edit-clear'))
        clear_action.triggered.connect(self.__search.clear)
        self.__search.addAction(clear_action, QtWidgets.QLineEdit.TrailingPosition)

        self.__sort_mode = QtWidgets.QComboBox(self)
        self.__sort_mode.addItem("Name", 'name')
        self.__sort_mode.addItem("Last usage", 'mtime')
        self.__sort_mode.currentIndexChanged.connect(self.__updateSort)

        self.__sort_dir = QtWidgets.QComboBox(self)
        self.__sort_dir.addItem("Ascending", 'asc')
        self.__sort_dir.addItem("Descending", 'desc')
        self.__sort_dir.currentIndexChanged.connect(self.__updateSort)

        self.__open_button = QtWidgets.QPushButton(self)
        self.__open_button.setIcon(QtGui.QIcon.fromTheme('document-open'))
        self.__open_button.setText("Open")
        self.__open_button.setDisabled(True)
        self.__open_button.clicked.connect(self.__openClicked)

        self.__new_project_button = QtWidgets.QPushButton(self)
        self.__new_project_button.setIcon(QtGui.QIcon.fromTheme('document-new'))
        self.__new_project_button.setText("New project")
        self.__new_project_button.clicked.connect(self.__newProjectClicked)

        self.__new_folder_button = QtWidgets.QPushButton(self)
        self.__new_folder_button.setIcon(QtGui.QIcon.fromTheme('folder-new'))
        self.__new_folder_button.setText("New folder")
        self.__new_folder_button.setDisabled(True)
        self.__new_folder_button.clicked.connect(self.__newFolderClicked)

        self.__delete_action = QtWidgets.QAction("Delete", self)
        self.__delete_action.setIcon(QtGui.QIcon.fromTheme('edit-delete'))
        self.__delete_action.setEnabled(False)
        self.__delete_action.triggered.connect(self.__deleteClicked)

        self.__archive_action = QtWidgets.QAction("Archive", self)
        self.__archive_action.setEnabled(False)
        self.__archive_action.triggered.connect(self.__archiveClicked)

        self.__more_menu = QtWidgets.QMenu()
        self.__more_menu.addAction(self.__delete_action)
        self.__more_menu.addAction(self.__archive_action)

        self.__more_button = QtWidgets.QPushButton(self)
        self.__more_button.setText("More")
        self.__more_button.setMenu(self.__more_menu)
        self.__more_button.setDisabled(True)

        self.__filter_model = FilterModel()
        self.__filter_model.setSourceModel(FlatProjectListModel(self.__project_registry))
        self.__filter_model.setSortRole(project_registry_lib.Project.NameRole)
        self.__filter_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.__filter_model.sort(0, Qt.AscendingOrder)
        self.__filter_model.setFilterKeyColumn(0)
        self.__filter_model.setFilterRole(project_registry_lib.Project.NameRole)
        self.__search.textChanged.connect(self.__filter_model.setFilterWords)

        self.__list = ProjectListView(self)
        self.__list.setModel(self.__filter_model)
        self.__list.numProjectsSelected.connect(lambda count: self.__updateButtons(count == 1))
        self.__list.itemDoubleClicked.connect(self.openProject)

        l4 = QtWidgets.QHBoxLayout()
        l4.setContentsMargins(0, 0, 0, 0)
        l4.addWidget(self.__search)
        l4.addWidget(self.__sort_mode)
        l4.addWidget(self.__sort_dir)

        l3 = QtWidgets.QVBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__open_button)
        l3.addWidget(self.__new_project_button)
        l3.addWidget(self.__new_folder_button)
        l3.addWidget(self.__more_button)
        l3.addStretch(1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__list)
        l2.addLayout(l3)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addLayout(l4)
        l1.addLayout(l2)
        self.setLayout(l1)

    def cleanup(self) -> None:
        pass

    def __updateButtons(self, enable: bool) -> None:
        self.__open_button.setDisabled(not enable)
        self.__more_button.setDisabled(not enable)
        self.__delete_action.setEnabled(enable)

    def __updateSort(self) -> None:
        sort_mode = self.__sort_mode.currentData()
        if sort_mode == 'name':
            self.__filter_model.setSortRole(project_registry_lib.Project.NameRole)
        else:
            assert sort_mode == 'mtime'
            self.__filter_model.setSortRole(project_registry_lib.Project.MTimeRole)

        sort_dir = self.__sort_dir.currentData()
        if sort_dir == 'asc':
            self.__filter_model.sort(0, Qt.AscendingOrder)
        else:
            assert sort_dir == 'desc'
            self.__filter_model.sort(0, Qt.DescendingOrder)

    def __openClicked(self) -> None:
        selected_projects = self.__list.selectedProjects()
        if len(selected_projects) == 1:
            self.openProject(selected_projects[0])

    def __newProjectClicked(self) -> None:
        dialog = NewProjectDialog(parent=self, context=self.context)
        dialog.setModal(True)
        dialog.finished.connect(functools.partial(self.__newProjectDialogDone, dialog))
        dialog.show()

    def __newProjectDialogDone(self, dialog: NewProjectDialog, result: int) -> None:
        if result != QtWidgets.QDialog.Accepted:
            return

        self.createProject.emit(dialog.projectPath())

    def __newFolderClicked(self) -> None:
        raise NotImplementedError

    def __deleteClicked(self) -> None:
        selected_projects = self.__list.selectedProjects()
        if len(selected_projects) == 1:
            project = selected_projects[0]

            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("noisicaä - Delete Project")
            dialog.setIcon(QtWidgets.QMessageBox.Warning)
            dialog.setText("Delete project \"%s\"?" % project.name)
            dialog.setInformativeText("All data will be irrevocably removed.")
            buttons = QtWidgets.QMessageBox.StandardButtons()
            buttons |= QtWidgets.QMessageBox.Ok
            buttons |= QtWidgets.QMessageBox.Cancel
            dialog.setStandardButtons(buttons)
            dialog.setModal(True)
            dialog.finished.connect(
                lambda result: self.call_async(
                    self.__deleteDialogDone(project, result)))
            dialog.show()

    async def __deleteDialogDone(
            self, project: project_registry_lib.Project, result: int
    ) -> None:
        if result != QtWidgets.QMessageBox.Ok:
            return

        self.setDisabled(True)
        await project.delete()
        await self.__project_registry.refresh()
        self.setDisabled(False)

    def __archiveClicked(self) -> None:
        raise NotImplementedError

    def openProject(self, project: project_registry_lib.Project) -> None:
        self.projectSelected.emit(project)
