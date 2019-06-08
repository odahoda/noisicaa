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
import shutil
import urllib.parse
from typing import cast, Any, List, Iterable, Iterator

from PyQt5.QtCore import Qt
from PyQt5 import QtCore

from noisicaa.core.typing_extra import down_cast
from noisicaa import music
from . import ui_base

logger = logging.getLogger(__name__)


class Item(object):
    def __init__(self, *, path: str) -> None:
        self.path = path
        self.parent = None  # type: Item
        self.index = 0
        self.children = []  # type: List[Item]

    def projects(self) -> Iterator['Project']:
        for child in self.children:
            yield from child.projects()

    def data(self, role: int) -> Any:
        return None

    def flags(self) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.NoItemFlags)


class Root(Item):
    def __init__(self) -> None:
        super().__init__(path='<root>')


class Project(ui_base.CommonMixin, Item):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.client = None  # type: music.ProjectClient

    def projects(self) -> Iterator['Project']:
        yield self
        yield from super().projects()

    def flags(self) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def data(self, role: int) -> Any:
        if role == Qt.UserRole:
            return self.path

        elif role == Qt.DisplayRole:
            return os.path.splitext(os.path.basename(self.path))[0]

        return None

    @property
    def name(self) -> str:
        return urllib.parse.unquote(os.path.splitext(os.path.basename(self.path))[0])

    async def __create_process(self) -> None:
        self.client = music.ProjectClient(
            event_loop=self.event_loop,
            server=self.app.process.server,
            node_db=self.app.node_db,
            urid_mapper=self.app.urid_mapper,
            manager=self.app.process.manager,
            tmp_dir=self.app.process.tmp_dir,
        )
        await self.client.setup()

    async def open(self) -> None:
        await self.__create_process()
        await self.client.open(self.path)

    async def create(self) -> None:
        await self.__create_process()
        await self.client.create(self.path)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            await self.client.cleanup()
            self.client = None

    async def delete(self) -> None:
        os.unlink(self.path)
        data_dir = os.path.join(
            os.path.dirname(self.path),
            os.path.basename(self.path)[:-6] + '.data')
        shutil.rmtree(data_dir)


class ProjectRegistry(ui_base.CommonMixin, QtCore.QAbstractItemModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__root = Root()

    async def setup(self) -> None:
        await self.refresh()

    async def cleanup(self) -> None:
        for project in self.__root.projects():
            await project.close()
        self.__root = None

    def __scan_projects(self, directories: Iterable[str]) -> List[str]:
        paths = []  # type: List[str]
        for directory in directories:
            directory = os.path.expanduser(directory)
            directory = os.path.abspath(directory)
            logger.info("Scanning project directory %s...", directory)
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    if filename.endswith('.noise'):
                        data_dir_name = filename[:-6] + '.data'
                        if data_dir_name in dirnames:
                            dirnames.remove(data_dir_name)
                            paths.append(os.path.join(dirpath, filename))

        return paths

    def projects(self) -> List[Project]:
        return list(self.__root.projects())

    async def refresh(self) -> None:
        # TODO: get list of directories from settings
        directories = ['~/Music/Noisicaä', '/lala']

        paths = await self.event_loop.run_in_executor(None, self.__scan_projects, directories)

        old_paths = {project.path for project in self.__root.projects()}
        new_paths = set(paths)

        for path in old_paths - new_paths:
            logger.info("Removing project at %s...", path)

            for idx, project in enumerate(self.__root.children):
                if project.path == path:
                    self.beginRemoveRows(QtCore.QModelIndex(), idx, idx)
                    del self.__root.children[idx]
                    for idx, item in enumerate(self.__root.children[idx:], idx):
                        item.index = idx
                    self.endRemoveRows()
                    await project.close()
                    break

        for path in new_paths - old_paths:
            logger.error("Adding project at %s...", path)

            idx = 0
            while idx < len(self.__root.children) and path > self.__root.children[idx].path:
                idx += 1

            project = Project(path=path, context=self.context)
            project.parent = self.__root

            self.beginInsertRows(QtCore.QModelIndex(), idx, idx)
            self.__root.children.insert(idx, project)
            for idx, item in enumerate(self.__root.children[idx:], idx):
                item.index = idx
            self.endInsertRows()

    def item(self, index: QtCore.QModelIndex = QtCore.QModelIndex()) -> Item:
        if not index.isValid():
            return self.__root
        else:
            return down_cast(Item, index.internalPointer())

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        parent_item = self.item(parent)
        return self.createIndex(row, column, parent_item.children[row])

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore
        if not index.isValid():
            return QtCore.QModelIndex()

        item = down_cast(Item, index.internalPointer())
        if item is self.__root:
            return QtCore.QModelIndex()

        return self.createIndex(item.parent.index, 0, item.parent)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 1

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        parent_item = self.item(parent)
        if parent_item is None:
            return 0
        return len(parent_item.children)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        return self.item(index).flags()

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        return self.item(index).data(role)

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        return None
