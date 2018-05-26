#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Iterator, Set  # pylint: disable=unused-import

logger = logging.getLogger(__name__)


class Selectable(object):
    selection_class = None  # type: str

    def setSelected(self, selected: bool) -> None:
        raise NotImplementedError


class SelectionSet(object):
    def __init__(self) -> None:
        self.__selection_set = set()  # type: Set[Selectable]

    def __iter__(self) -> Iterator[Selectable]:
        yield from self.__selection_set

    def empty(self) -> bool:
        return len(self.__selection_set) == 0

    def clear(self) -> None:
        for obj in self.__selection_set:
            obj.setSelected(False)
        self.__selection_set.clear()

    def add(self, obj: Selectable) -> None:
        if obj in self.__selection_set:
            raise RuntimeError("Item already selected.")

        logger.info("Adding to selection: %s", obj)

        assert obj.selection_class is not None

        self.__selection_set.add(obj)
        obj.setSelected(True)

    def remove(self, obj: Selectable, update_object: bool = True) -> None:
        if obj not in self.__selection_set:
            raise RuntimeError("Item not selected.")

        logger.info("Removing selection: %s", obj)

        self.__selection_set.remove(obj)
        if update_object:
            obj.setSelected(False)
