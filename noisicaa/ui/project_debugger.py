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
import os
import os.path
import time
import traceback
from typing import cast, Any, Dict, Union

from PySide2.QtCore import Qt
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

from noisicaa import constants
from noisicaa.core import storage
from noisicaa.music import mutations_pb2
from . import ui_base
from . import project_registry

logger = logging.getLogger(__name__)


class MutationModel(QtCore.QAbstractItemModel):
    COL_DIR = 0
    COL_TIME = 1
    COL_NAME = 2

    def __init__(self, project_storage: storage.ProjectStorage) -> None:
        super().__init__()

        self.__storage = project_storage
        self.__mutation_cache = {}  # type: Dict[int, Union[str, mutations_pb2.MutationList]]
        self.__truncate_index = None  # type: int

    def __getMutationList(self, idx: int) -> Union[str, mutations_pb2.MutationList]:
        try:
            return self.__mutation_cache[idx]
        except KeyError:
            log_entry = self.__storage.get_log_entry(idx)
            mutation_list = mutations_pb2.MutationList()
            try:
                parsed_bytes = mutation_list.ParseFromString(log_entry)  # type: ignore
                assert parsed_bytes == len(log_entry)
            except Exception as exc:  # pylint: disable=broad-except
                error = self.__mutation_cache[idx] = str(exc)
                return error
            else:
                self.__mutation_cache[idx] = mutation_list
                return mutation_list

    def setTruncateIndex(self, index: int) -> None:
        self.__truncate_index = index
        self.dataChanged.emit(
            self.createIndex(0, 0, None),
            self.createIndex(self.rowCount() - 1, self.columnCount() - 1),
            [Qt.FontRole])

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        return self.createIndex(row, column, None)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore
        return QtCore.QModelIndex()

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 3

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return self.__storage.next_sequence_number

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        history_entry = self.__storage.get_history_entry(index.row())

        if role == Qt.DisplayRole:
            if index.column() == self.COL_DIR:
                return {b'f': 'Forward', b'b': 'Backward'}.get(history_entry[0], history_entry[0])

            elif index.column() in (self.COL_NAME, self.COL_TIME):
                mutations = self.__getMutationList(history_entry[1])
                if isinstance(mutations, mutations_pb2.MutationList):
                    if index.column() == self.COL_NAME:
                        return mutations.name
                    elif index.column() == self.COL_TIME:
                        return time.ctime(mutations.timestamp)
                else:
                    return mutations

        elif role == Qt.BackgroundColorRole:
            if index.column() == self.COL_DIR:
                if history_entry[0] == b'b':
                    return QtGui.QColor(255, 255, 200)

            elif index.column() in (self.COL_NAME, self.COL_TIME):
                mutations = self.__getMutationList(history_entry[1])
                if isinstance(mutations, mutations_pb2.MutationList):
                    return None
                else:
                    return QtGui.QColor(255, 200, 200)

        elif role == Qt.DecorationRole:
            if index.column() in (self.COL_NAME, self.COL_TIME):
                mutations = self.__getMutationList(history_entry[1])
                if isinstance(mutations, mutations_pb2.MutationList):
                    return None
                else:
                    return QtGui.QIcon(
                        os.path.join(constants.DATA_DIR, 'icons', 'dialog-warning.svg'))

        elif role == Qt.FontRole:
            if self.__truncate_index is not None and index.row() >= self.__truncate_index:
                font = QtGui.QFont()
                font.setStrikeOut(True)
                return font

        return None

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return {
                    self.COL_DIR: "Dir",
                    self.COL_NAME: "Log",
                    self.COL_TIME: "Time",
                }[section]

            elif orientation == Qt.Vertical:
                return str(section)

        return None


class ProjectDebugger(ui_base.CommonMixin, QtWidgets.QWidget):
    def __init__(
            self, *,
            project: project_registry.Project,
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__project = project
        self.__storage = None  # type: storage.ProjectStorage
        self.__mutation_model = None  # type: MutationModel
        self.__truncate_index = None  # type: int

        self.__mutations = QtWidgets.QTableView(self)
        self.__mutations.horizontalHeader().setVisible(True)
        self.__mutations.horizontalHeader().setStretchLastSection(True)
        self.__mutations.verticalHeader().setVisible(True)
        self.__mutations.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.__mutations.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.__mutation_list = QtWidgets.QTextEdit(self)

        self.__truncate_button = QtWidgets.QPushButton(self)
        self.__truncate_button.setText("Truncate log")
        self.__truncate_button.clicked.connect(self.__truncateClicked)

        self.__revert_button = QtWidgets.QPushButton(self)
        self.__revert_button.setText("Revert changes")
        self.__revert_button.setEnabled(False)
        self.__revert_button.clicked.connect(self.__revertClicked)

        self.__apply_button = QtWidgets.QPushButton(self)
        self.__apply_button.setText("Apply changes")
        self.__apply_button.setEnabled(False)
        self.__apply_button.clicked.connect(self.__applyClicked)

        l2 = QtWidgets.QHBoxLayout()
        l2.addWidget(self.__truncate_button)
        l2.addStretch(1)
        l2.addWidget(self.__revert_button)
        l2.addWidget(self.__apply_button)

        splitter = QtWidgets.QSplitter(self)
        splitter.addWidget(self.__mutations)
        splitter.addWidget(self.__mutation_list)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(splitter)
        l1.addLayout(l2)
        self.setLayout(l1)

    @property
    def project(self) -> project_registry.Project:
        return self.__project

    async def setup(self) -> None:
        self.__project.startDebugger()

        self.__storage = storage.ProjectStorage()
        self.__storage.open(self.__project.path)

        self.__initMutations()

    async def cleanup(self) -> None:
        if self.__storage is not None:
            self.__storage.close()
            self.__storage = None

        self.__mutations.setModel(None)
        self.__mutation_model = None

        self.__project.endDebugger()

    def __initMutations(self) -> None:
        self.__mutation_model = MutationModel(self.__storage)
        self.__mutations.setModel(self.__mutation_model)
        self.__mutations.resizeColumnToContents(MutationModel.COL_DIR)
        self.__mutations.resizeColumnToContents(MutationModel.COL_TIME)
        self.__mutations.selectionModel().currentRowChanged.connect(
            lambda idx, _: self.__updateMutationList(idx.row()))

    def __updateMutationList(self, idx: int) -> None:
        history_entry = self.__storage.get_history_entry(idx)
        log_entry = self.__storage.get_log_entry(history_entry[1])
        mutation_list = mutations_pb2.MutationList()
        try:
            parsed_bytes = mutation_list.ParseFromString(log_entry)  # type: ignore
            assert parsed_bytes == len(log_entry)
        except Exception:  # pylint: disable=broad-except
            self.__mutation_list.setPlainText(traceback.format_exc())
        else:
            self.__mutation_list.setPlainText(str(mutation_list))

    def __truncateClicked(self) -> None:
        current_index = self.__mutations.selectionModel().currentIndex()
        if current_index.isValid():
            self.__truncate_index = current_index.row()
            self.__mutation_model.setTruncateIndex(self.__truncate_index)
            self.__revert_button.setEnabled(True)
            self.__apply_button.setEnabled(True)

    def __revertClicked(self) -> None:
        self.__truncate_index = None
        self.__mutation_model.setTruncateIndex(None)
        self.__revert_button.setEnabled(False)
        self.__apply_button.setEnabled(False)

    def __applyClicked(self) -> None:
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("noisicaä - Project debugger")
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setText("Apply changes to project \"%s\"?" % self.__project.name)
        dialog.setInformativeText(
            "The changes cannot be reverted. Data might get lost and the"
            " project permanently corrupted.")
        buttons = QtWidgets.QMessageBox.StandardButtons()
        buttons |= QtWidgets.QMessageBox.Apply
        buttons |= QtWidgets.QMessageBox.Cancel
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if dialog.exec_() == QtWidgets.QMessageBox.Apply:
            self.__storage.close()

            if self.__truncate_index is not None:
                os.truncate(
                    os.path.join(self.__project.path, 'log.history'),
                    self.__storage.log_history_formatter.size * self.__truncate_index)
                self.__truncate_index = None

            self.__storage.open(self.__project.path)
            self.__initMutations()
