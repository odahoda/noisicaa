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

import bisect
import logging
import pathlib
from typing import cast, Any, Optional, Iterator, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore

from noisicaa import instrument_db
from noisicaa import core
from . import ui_base

logger = logging.getLogger(__name__)


class Item(object):
    def __init__(self, *, parent: Optional['AbstractFolder']) -> None:
        self.parent = parent

    def __lt__(self, other: object) -> bool:
        return self.key < cast(Item, other).key

    @property
    def key(self) -> Tuple[int, str, str]:
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        raise NotImplementedError

    def walk(self) -> Iterator['Item']:
        yield self


class AbstractFolder(Item):  # pylint: disable=abstract-method
    def __init__(self, *, path: pathlib.Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.path = path
        self.children = []  # type: List[Item]

    def walk(self) -> Iterator['Item']:
        yield from super().walk()
        for child in self.children:
            yield from child.walk()


class Root(AbstractFolder):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(parent=None, **kwargs)

    @property
    def key(self) -> Tuple[int, str, str]:
        return (0, str(self.path).lower(), str(self.path))

    @property
    def display_name(self) -> str:
        return '[root]'


class Folder(AbstractFolder):
    @property
    def key(self) -> Tuple[int, str, str]:
        return (0, str(self.path).lower(), str(self.path))

    @property
    def display_name(self) -> str:
        return str(self.path)


class Instrument(Item):
    def __init__(
            self, *, description: instrument_db.InstrumentDescription, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.description = description

    @property
    def key(self) -> Tuple[int, str, str]:
        return (0, self.description.display_name.lower(), self.description.uri)

    @property
    def display_name(self) -> str:
        return self.description.display_name


class InstrumentList(ui_base.CommonMixin, QtCore.QAbstractItemModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__instrument_mutation_listener = None  # type: core.Listener

        self.__root_item = Root(path='/')

    def setup(self) -> None:
        for description in self.app.instrument_db.instruments:
            self.addInstrument(description)

        self.__instrument_mutation_listener = self.app.instrument_db.mutation_handlers.add(
            self.__handleInstrumentMutation)

    def cleanup(self) -> None:
        self.__root_item = None

        if self.__instrument_mutation_listener is not None:
            self.__instrument_mutation_listener.remove()
            self.__instrument_mutation_listener = None

    def clear(self) -> None:
        self.__root_item = Root(path='/')

    def __handleInstrumentMutation(self, mutation: instrument_db.Mutation) -> None:
        if mutation.WhichOneof('type') == 'add_instrument':
            self.addInstrument(mutation.add_instrument)
        else:
            raise TypeError(type(mutation))

    def addInstrument(self, description: instrument_db.InstrumentDescription) -> None:
        parent = self.__root_item  # type: AbstractFolder
        parent_index = self.indexForItem(parent)

        if description.format == instrument_db.InstrumentDescription.SF2:
            folder_path = pathlib.Path(description.path)
        else:
            folder_path = pathlib.Path(description.path).parent

        folder_parts = folder_path.parts
        assert len(folder_parts) > 0, description.path
        while folder_parts:
            for folder_idx, folder in enumerate(parent.children):
                if not isinstance(folder, AbstractFolder):
                    continue

                match_length = 0
                for idx, part in enumerate(folder.path.parts):
                    if part != folder_parts[idx]:
                        break
                    match_length += 1

                if match_length > 0:
                    break

            else:
                folder = Folder(path=pathlib.Path(*folder_parts), parent=parent)
                match_length = len(folder_parts)
                folder_idx = bisect.bisect(parent.children, folder)
                self.beginInsertRows(parent_index, folder_idx, folder_idx)
                parent.children.insert(folder_idx, folder)
                self.endInsertRows()

            assert folder_parts[:match_length] == folder.path.parts[:match_length]

            if match_length < len(folder.path.parts):
                self.beginRemoveRows(parent_index, folder_idx, folder_idx)
                old_folder = cast(Folder, parent.children.pop(folder_idx))
                self.endRemoveRows()

                folder = Folder(path=pathlib.Path(*folder_parts[:match_length]), parent=parent)
                folder_idx = bisect.bisect(parent.children, folder)
                self.beginInsertRows(parent_index, folder_idx, folder_idx)
                parent.children.insert(folder_idx, folder)
                self.endInsertRows()

                new_folder = Folder(path=pathlib.Path(
                    *old_folder.path.parts[match_length:]), parent=folder)
                for child in old_folder.children:
                    child.parent = new_folder
                    new_folder.children.append(child)
                new_folder_idx = bisect.bisect(folder.children, folder)
                self.beginInsertRows(self.indexForItem(folder), new_folder_idx, new_folder_idx)
                folder.children.insert(folder_idx, new_folder)
                self.endInsertRows()

            folder_parts = folder_parts[match_length:]

            parent = folder
            parent_index = self.indexForItem(folder)

        instr = Instrument(
            description=description,
            parent=parent)
        insert_pos = bisect.bisect(parent.children, instr)

        self.beginInsertRows(parent_index, insert_pos, insert_pos)
        parent.children.insert(insert_pos, instr)
        self.endInsertRows()

    def instruments(self) -> Iterator[Instrument]:
        for item in self.__root_item.walk():
            if isinstance(item, Instrument):
                yield item

    def flattened(self, parent: Optional[AbstractFolder] = None) -> Iterator[List[str]]:
        if parent is None:
            parent = self.__root_item

        path = []  # type: List[str]
        folder = parent  # type: AbstractFolder
        while folder.parent is not None:
            path.insert(0, folder.display_name)
            folder = folder.parent

        if path:
            yield path

        for item in parent.children:
            if isinstance(item, Instrument):
                yield path + [item.display_name]
            elif isinstance(item, AbstractFolder):
                yield from self.flattened(item)

    def item(self, index: QtCore.QModelIndex) -> Item:
        if not index.isValid():
            raise ValueError("Invalid index")

        item = index.internalPointer()
        assert item is not None
        return item

    def indexForItem(self, item: Item, column: int = 0) -> QtCore.QModelIndex:
        if item.parent is None:
            return QtCore.QModelIndex()
        else:
            return self.createIndex(item.parent.children.index(item), column, item)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.column() > 0:  # pragma: no coverage
            return 0

        if not parent.isValid():
            return len(self.__root_item.children)

        parent_item = parent.internalPointer()
        if parent_item is None:
            return 0

        if isinstance(parent_item, AbstractFolder):
            return len(parent_item.children)
        else:
            return 0

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 1

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        if not parent.isValid():
            return self.createIndex(row, column, self.__root_item.children[row])

        parent_item = parent.internalPointer()
        assert isinstance(parent_item, AbstractFolder), parent_item.track

        item = parent_item.children[row]
        return self.createIndex(row, column, item)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer()
        if item is None or item.parent is None:
            return QtCore.QModelIndex()

        return self.indexForItem(item.parent)

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():  # pragma: no coverage
            return None

        item = index.internalPointer()
        if item is None:
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0:
                return item.display_name

        return None  # pragma: no coverage

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        return None
