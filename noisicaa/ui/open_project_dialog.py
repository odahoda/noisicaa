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
from typing import Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import humanize

from noisicaa import constants
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

        self.__opened = QtWidgets.QLabel(self)
        self.__opened.setText("[open]")
        opened_font = QtGui.QFont(self.__opened.font())
        opened_font.setPointSizeF(1.4 * opened_font.pointSizeF())
        opened_font.setBold(True)
        self.__opened.setFont(opened_font)
        opened_palette = QtGui.QPalette(self.__opened.palette())
        opened_palette.setColor(QtGui.QPalette.Text, Qt.red)
        opened_palette.setColor(QtGui.QPalette.HighlightedText, Qt.red)
        self.__opened.setPalette(opened_palette)

        self.__name = QtWidgets.QLabel(self)
        name_font = QtGui.QFont(self.__name.font())
        name_font.setPointSizeF(1.4 * name_font.pointSizeF())
        name_font.setBold(True)
        self.__name.setFont(name_font)

        self.__path = QtWidgets.QLabel(self)
        self.__mtime = QtWidgets.QLabel(self)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__opened)
        l2.addWidget(self.__name, 1)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addLayout(l2)
        l1.addWidget(self.__path)
        l1.addWidget(self.__mtime)
        self.setLayout(l1)

    def updateContents(self) -> None:
        self.__opened.setVisible(self.__project.isOpened())
        self.__name.setText(self.__project.name)
        self.__path.setText(self.__project.path)
        self.__mtime.setText(
            'Last usage: %s' % humanize.naturaltime(
                datetime.datetime.fromtimestamp(self.__project.mtime)))


class ItemDelegate(QtWidgets.QAbstractItemDelegate):
    def __init__(self) -> None:
        super().__init__()

        self.__widgets = {}  # type: Dict[str, QtWidgets.QWidget]

    def __getWidget(self, index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        item = index.model().item(index)
        if item is None:
            logger.error("Index without item: %d,%d", index.row(), index.column())
            path = '<invalid>'
        else:
            path = item.path

        if path not in self.__widgets:
            widget = None  # type: QtWidgets.QWidget
            if isinstance(item, project_registry_lib.Project):
                widget = ProjectItem(item)
            elif isinstance(item, project_registry_lib.Root) or item is None:
                widget = QtWidgets.QWidget()
            else:
                raise TypeError("%s: %s" % (path, type(item)))
            self.__widgets[path] = widget

        return self.__widgets[path]

    def paint(
            self,
            painter: QtGui.QPainter,
            option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex
    ) -> None:
        widget = self.__getWidget(index)
        widget.resize(option.rect.size())
        widget.updateContents()
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

        self.__update_timer = QtCore.QTimer(self)
        self.__update_timer.timeout.connect(lambda: self.viewport().update())
        self.__update_timer.setInterval(300)
        self.__update_timer.start()

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


class FlatProjectListModel(QtCore.QAbstractProxyModel):
    def __init__(self, project_registry: project_registry_lib.ProjectRegistry) -> None:
        super().__init__()

        self.__registry = project_registry
        self.setSourceModel(self.__registry)

        self.__registry.rowsAboutToBeInserted.connect(
            lambda parent, r1, r2: self.beginInsertRows(self.mapFromSource(parent), r1, r2))
        self.__registry.rowsInserted.connect(self.endInsertRows)
        self.__registry.rowsAboutToBeRemoved.connect(
            lambda parent, r1, r2: self.beginRemoveRows(self.mapFromSource(parent), r1, r2))
        self.__registry.rowsRemoved.connect(self.endRemoveRows)
        self.__registry.dataChanged.connect(
            lambda topLeft, bottomRight, roles: self.dataChanged.emit(
                self.index(0), self.index(self.rowCount() - 1), roles))

        self.__root = QtCore.QModelIndex()

    def item(self, index: QtCore.QModelIndex = QtCore.QModelIndex()) -> project_registry_lib.Item:
        return self.__registry.item(self.mapToSource(index))

    def mapFromSource(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        if not index.isValid():
            return QtCore.QModelIndex()
        return self.createIndex(index.row(), index.column(), QtCore.QModelIndex())

    def mapToSource(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        return self.__registry.index(index.row(), index.column(), self.__root)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return self.__registry.rowCount(self.__root)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return self.__registry.columnCount(self.__root)

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        return self.createIndex(row, column, None)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore
        return QtCore.QModelIndex()


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
        self.__create_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'document-new.svg')))
        self.__create_button.setText("Create")
        self.__create_button.clicked.connect(self.accept)

        self.__close_button = QtWidgets.QPushButton(self)
        self.__close_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'window-close.svg')))
        self.__close_button.setText("Cancel")
        self.__close_button.clicked.connect(self.reject)

        self.__name = QtWidgets.QLineEdit(self)
        self.__name.textChanged.connect(self.__nameChanged)

        self.__error = QtWidgets.QLabel(self)
        palette = QtGui.QPalette(self.__error.palette())
        palette.setColor(QtGui.QPalette.WindowText, Qt.red)
        self.__error.setPalette(palette)

        self.__prev_name = QtWidgets.QToolButton(self)
        self.__prev_name.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'go-previous.svg')))
        self.__prev_name.clicked.connect(self.__prevNameClicked)

        self.__next_name = QtWidgets.QToolButton(self)
        self.__next_name.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'go-next.svg')))
        self.__next_name.clicked.connect(self.__nextNameClicked)

        self.__name_seed = random.randint(0, 1000000)
        self.__generateName()
        self.__name.setFocus()
        self.__name.selectAll()

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
        filename = self.projectName()
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
    debugProject = QtCore.pyqtSignal(project_registry_lib.Project)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setObjectName('open-project-dialog')

        self.__filter_model = FilterModel()
        self.__filter_model.setSourceModel(FlatProjectListModel(self.app.project_registry))
        self.__filter_model.setSortRole(project_registry_lib.Project.NameRole)
        self.__filter_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.__filter_model.sort(0, Qt.AscendingOrder)
        self.__filter_model.setFilterKeyColumn(0)
        self.__filter_model.setFilterRole(project_registry_lib.Project.NameRole)

        self.__search = QtWidgets.QLineEdit(self)
        search_action = QtWidgets.QAction(self.__search)
        search_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-find.svg')))
        self.__search.addAction(search_action, QtWidgets.QLineEdit.LeadingPosition)
        clear_action = QtWidgets.QAction("Clear search string", self.__search)
        clear_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-clear.svg')))
        clear_action.triggered.connect(self.__search.clear)
        self.__search.addAction(clear_action, QtWidgets.QLineEdit.TrailingPosition)
        self.__search.textChanged.connect(self.__filter_model.setFilterWords)
        self.__search.setText(
            self.app.settings.value('open-project-dialog/search-text', ''))
        self.__search.textChanged.connect(
            lambda text: self.app.settings.setValue('open-project-dialog/search-text', text))

        self.__sort_mode = QtWidgets.QComboBox(self)
        self.__sort_mode.addItem("Name", 'name')
        self.__sort_mode.addItem("Last usage", 'mtime')
        self.__sort_mode.setCurrentIndex(self.__sort_mode.findData(
            self.app.settings.value('open-project-dialog/sort-mode', 'name')))
        self.__sort_mode.currentIndexChanged.connect(self.__updateSort)

        self.__sort_dir = QtWidgets.QComboBox(self)
        self.__sort_dir.addItem("Ascending", 'asc')
        self.__sort_dir.addItem("Descending", 'desc')
        self.__sort_dir.setCurrentIndex(self.__sort_dir.findData(
            self.app.settings.value('open-project-dialog/sort-dir', 'asc')))
        self.__sort_dir.currentIndexChanged.connect(self.__updateSort)

        self.__updateSort()

        self.__open_button = QtWidgets.QPushButton(self)
        self.__open_button.setObjectName('open')
        self.__open_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'document-open.svg')))
        self.__open_button.setText("Open")
        self.__open_button.clicked.connect(self.__openClicked)

        self.__new_project_button = QtWidgets.QPushButton(self)
        self.__new_project_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'document-new.svg')))
        self.__new_project_button.setText("New project")
        self.__new_project_button.clicked.connect(self.__newProjectClicked)

        self.__delete_action = QtWidgets.QAction("Delete", self)
        self.__delete_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-delete.svg')))
        self.__delete_action.triggered.connect(self.__deleteClicked)

        self.__debugger_action = QtWidgets.QAction("Open in debugger", self)
        self.__debugger_action.triggered.connect(self.__debuggerClicked)

        self.__more_menu = QtWidgets.QMenu()
        self.__more_menu.addAction(self.__delete_action)
        self.__more_menu.addAction(self.__debugger_action)

        self.__more_button = QtWidgets.QPushButton(self)
        self.__more_button.setText("More")
        self.__more_button.setMenu(self.__more_menu)

        self.__list = ProjectListView(self)
        self.__list.setObjectName('project-list')
        self.__list.setModel(self.__filter_model)
        self.__list.numProjectsSelected.connect(lambda _: self.__updateButtons())
        self.__list.itemDoubleClicked.connect(self.__itemDoubleClicked)

        self.__updateButtons()
        self.app.project_registry.contentsChanged.connect(self.__updateButtons)

        l4 = QtWidgets.QHBoxLayout()
        l4.setContentsMargins(0, 0, 0, 0)
        l4.addWidget(self.__search)
        l4.addWidget(self.__sort_mode)
        l4.addWidget(self.__sort_dir)

        l3 = QtWidgets.QVBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__open_button)
        l3.addWidget(self.__new_project_button)
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

    def __updateButtons(self) -> None:
        selected_projects = self.__list.selectedProjects()

        self.__open_button.setEnabled(
            len(selected_projects) == 1 and not selected_projects[0].isOpened())
        self.__delete_action.setEnabled(
            len(selected_projects) == 1 and not selected_projects[0].isOpened())
        self.__debugger_action.setEnabled(
            len(selected_projects) == 1 and not selected_projects[0].isOpened())

    def __updateSort(self) -> None:
        sort_mode = self.__sort_mode.currentData()
        if sort_mode == 'name':
            self.__filter_model.setSortRole(project_registry_lib.Project.NameRole)
        else:
            assert sort_mode == 'mtime'
            self.__filter_model.setSortRole(project_registry_lib.Project.MTimeRole)
        self.app.settings.setValue('open-project-dialog/sort-mode', sort_mode)

        sort_dir = self.__sort_dir.currentData()
        if sort_dir == 'asc':
            self.__filter_model.sort(0, Qt.AscendingOrder)
        else:
            assert sort_dir == 'desc'
            self.__filter_model.sort(0, Qt.DescendingOrder)
        self.app.settings.setValue('open-project-dialog/sort-dir', sort_dir)

    def __itemDoubleClicked(self, item: project_registry_lib.Item) -> None:
        if isinstance(item, project_registry_lib.Project) and not item.isOpened():
            self.openProject(item)

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
        await self.app.project_registry.refresh()
        self.setDisabled(False)

    def __debuggerClicked(self) -> None:
        selected_projects = self.__list.selectedProjects()
        if len(selected_projects) == 1:
            self.debugProject.emit(selected_projects[0])

    def openProject(self, project: project_registry_lib.Project) -> None:
        self.projectSelected.emit(project)
