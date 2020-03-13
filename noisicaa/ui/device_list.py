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
from typing import cast, Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa.ui import slots

logger = logging.getLogger(__name__)


class ModelItem(object):
    def __init__(self, parent: 'ModelItem') -> None:
        self.parent = parent
        self.index = 0
        self.children = []  # type: List[ModelItem]

    def data(self, role: int) -> Any:
        return None

    def flags(self) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.NoItemFlags)

    def insert(self, idx: int, item: 'ModelItem') -> None:
        self.children.insert(idx, item)
        for idx, child in enumerate(self.children):
            child.index = idx

    def remove(self, idx: int) -> None:
        del self.children[idx]
        for idx, child in enumerate(self.children):
            child.index = idx


class RootItem(ModelItem):
    def __init__(self) -> None:
        super().__init__(parent=None)


class DeviceItem(ModelItem):
    def __init__(self, device: audioproc.DeviceDescription, parent: 'RootItem') -> None:
        super().__init__(parent)
        self.device = device

    def flags(self) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.ItemIsEnabled)

    def data(self, role: int) -> Any:
        if role == Qt.UserRole:
            return self.device.uri

        elif role == Qt.DisplayRole:
            return self.device.display_name

        return None


class PortItem(ModelItem):
    def __init__(self, port: audioproc.DevicePortDescription, parent: 'DeviceItem') -> None:
        super().__init__(parent)
        self.port = port

    def flags(self) -> Qt.ItemFlags:
        return cast(Qt.ItemFlags, Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def data(self, role: int) -> Any:
        if role == Qt.UserRole:
            return self.port.uri

        elif role == Qt.DisplayRole:
            return self.port.display_name

        return None


class DeviceList(QtCore.QAbstractItemModel):
    def __init__(self) -> None:
        super().__init__()
        self.__root = RootItem()
        self.__devices = {}  # type: Dict[str, audioproc.DeviceDescription]
        self.__ports = {}  # type: Dict[str, audioproc.DevicePortDescription]

    def getDevice(self, uri: str) -> audioproc.DeviceDescription:
        return self.__devices[uri]

    def getPort(self, uri: str) -> audioproc.DevicePortDescription:
        return self.__ports[uri]

    def addDevice(self, device: audioproc.DeviceDescription) -> None:
        for item in self.__root.children:
            assert isinstance(item, DeviceItem)
            if item.device.uri == device.uri:
                logger.error("Duplicate device %s", device.uri)
                return

        new_item = DeviceItem(device, self.__root)
        for port in device.ports:
            new_item.insert(len(new_item.children), PortItem(port, new_item))
            self.__ports[port.uri] = port

        for i, item in enumerate(self.__root.children):
            assert isinstance(item, DeviceItem)
            if item.device.display_name.lower() > device.display_name.lower():
                insert_pos = i
                break
        else:
            insert_pos = len(self.__root.children)

        self.beginInsertRows(QtCore.QModelIndex(), insert_pos, insert_pos)
        self.__root.insert(insert_pos, new_item)
        self.endInsertRows()
        self.__devices[device.uri] = device

    def removeDevice(self, device: audioproc.DeviceDescription) -> None:
        for port in device.ports:
            self.__ports.pop(port.uri, None)
        self.__devices.pop(device.uri, None)

        for i, item in enumerate(self.__root.children):
            assert isinstance(item, DeviceItem)
            if item.device.uri == device.uri:
                self.beginRemoveRows(QtCore.QModelIndex(), i, i)
                self.__root.remove(i)
                self.endRemoveRows()
                break
        else:
            logger.error("Removal of unknown device %s requested", device.uri)

    def item(self, index: QtCore.QModelIndex = QtCore.QModelIndex()) -> ModelItem:
        if not index.isValid():
            return self.__root
        else:
            return down_cast(ModelItem, index.internalPointer())

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        parent_item = self.item(parent)
        return self.createIndex(row, column, parent_item.children[row])

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QtCore.QModelIndex()

        item = down_cast(ModelItem, index.internalPointer())
        parent = item.parent
        if parent is self.__root:
            return QtCore.QModelIndex()

        return self.createIndex(parent.index, 0, parent)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 1

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self.item(parent).children)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        return self.item(index).flags()

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
        return self.item(index).data(role)

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        return None


class FilteredDeviceList(QtCore.QSortFilterProxyModel):
    def __init__(self, source: DeviceList) -> None:
        super().__init__()

        self.setSourceModel(source)

        self.__source = source

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:
        parent_item = self.__source.item(parent)
        item = parent_item.children[row]

        if isinstance(item, DeviceItem):
            for child in item.children:
                assert isinstance(child, PortItem)
                if child.port.readable:
                    return True

        elif isinstance(item, PortItem):
            if item.port.readable:
                return True

        else:
            raise ValueError(type(item).__name__)

        return False


class PortSelector(slots.SlotContainer, QtWidgets.QComboBox):
    selectedPort, setSelectedPort, selectedPortChanged = slots.slot(str, 'selectedPort')

    def __init__(self, device_list: DeviceList, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent=parent)

        self.__device_list = device_list

        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)

        self.__filter = FilteredDeviceList(device_list)
        self.setModel(self.__filter)

        view = QtWidgets.QTreeView()
        view.setHeaderHidden(True)
        self.setView(view)
        view.expandAll()

        self.currentIndexChanged.connect(lambda: self.setSelectedPort(self.currentData()))
        self.selectedPortChanged.connect(self.__updateName)

    def __updateName(self, uri: str) -> None:
        try:
            port_name = self.__device_list.getPort(uri).display_name
        except KeyError:
            port_name = uri
        self.setEditText(port_name)
