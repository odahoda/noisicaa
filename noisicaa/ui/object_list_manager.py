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
import typing
from typing import Any, Dict, List, TypeVar

from PyQt5 import QtCore

from noisicaa import core
from noisicaa import music
from .qtyping import QGeneric

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    QObjectMixin = QtCore.QObject
else:
    QObjectMixin = object

OBJECT = TypeVar('OBJECT', bound=music.ObjectBase)
WRAPPER = TypeVar('WRAPPER', bound='ObjectWrapper')
MANAGER = TypeVar('MANAGER', bound='ObjectListManager')

class ObjectWrapper(QGeneric[OBJECT, MANAGER], QObjectMixin):
    def __init__(self, object_list_manager: MANAGER, wrapped_object: OBJECT, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__manager = object_list_manager
        self.__obj = wrapped_object

    def objectListManager(self) -> MANAGER:
        return self.__manager

    def wrappedObject(self) -> OBJECT:
        return self.__obj


class ObjectListManager(QGeneric[OBJECT, WRAPPER], core.AutoCleanupMixin, QObjectMixin):
    objectListChanged = QtCore.pyqtSignal()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__owner = None  # type: music.ObjectBase
        self.__list_attr = None  # type: str
        self.__list = None  # type: List[OBJECT]

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__wrappers = []  # type: List[WRAPPER]
        self.__id_map = {}  # type: Dict[int, WRAPPER]

    def initObjectList(self, owner: music.ObjectBase, attr: str) -> None:
        assert self.__owner is None
        self.__owner = owner
        self.__list_attr = attr
        self.__list = getattr(self.__owner, self.__list_attr)

        for index, obj in enumerate(self.__list):
            if self._filterObject(obj):
                self.__addObject(index, obj)
        self.__listeners['list'] = self.__owner.change_callbacks[self.__list_attr].add(
            self.__listChanged)

    def cleanup(self) -> None:
        while self.__wrappers:
            wrapper = self.__wrappers.pop(-1)
            self._deleteObjectWrapper(wrapper)
        self.__id_map.clear()

        self.__owner = None
        self.__list_attr = None
        self.__list = None

        super().cleanup()

    def __listChanged(self, change: music.PropertyListChange[OBJECT]) -> None:
        if isinstance(change, music.PropertyListInsert):
            if self._filterObject(change.new_value):
                self.__addObject(change.index, change.new_value)
            else:
                logger.error("Ignoring object %s (index=%d)", change.new_value, change.index)

        elif isinstance(change, music.PropertyListDelete):
            if change.old_value.id in self.__id_map:
                self.__removeObject(change.old_value)

        else:  # pragma: no cover
            raise TypeError(type(change))

    def __addObject(self, index: int, obj: OBJECT) -> None:
        logger.error("Adding object %s (index=%d)", obj, index)
        wrapper = self._createObjectWrapper(obj)

        self.__id_map[obj.id] = wrapper
        for i, w in enumerate(self.__wrappers):
            if w.wrappedObject().index > index:
                self.__wrappers.insert(i, wrapper)
                break
        else:
            self.__wrappers.append(wrapper)

        self.objectListChanged.emit()

    def __removeObject(self, obj: OBJECT) -> None:
        wrapper = self.__id_map[obj.id]
        assert wrapper.wrappedObject() is obj

        self._deleteObjectWrapper(wrapper)

        del self.__id_map[obj.id]
        for i, w in enumerate(self.__wrappers):
            if w is wrapper:
                del self.__wrappers[i]
                break
        else:
            raise RuntimeError

        self.objectListChanged.emit()

    def _filterObject(self, obj: music.ObjectBase) -> bool:
        return True

    def _createObjectWrapper(self, obj: OBJECT) -> WRAPPER:
        raise NotImplementedError

    def _deleteObjectWrapper(self, wrapper: WRAPPER) -> None:
        pass

    def objectWrappers(self) -> List[WRAPPER]:
        return self.__wrappers

    def objectWrapperById(self, obj_id: int) -> WRAPPER:
        return self.__id_map[obj_id]
