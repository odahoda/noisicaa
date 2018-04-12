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
import threading
from typing import Any, List, Optional, Tuple, Union, Generic, TypeVar

logger = logging.getLogger(__name__)

# Can't use real type, because that creates a circular dependency.
Registry = Any


class StatName(object):
    def __init__(self, **labels: Union[str, int]) -> None:
        self.__labels = labels

        self.__key = ':'.join(
            '%s=%s' % (k, v)
            for k, v in sorted(self.__labels.items()))

    def __str__(self) -> str:
        return self.__key
    __repr__ = __str__

    def __lt__(self, other: 'StatName') -> bool:
        return self.key < other.key

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StatName) and self.key == other.key

    def __hash__(self) -> int:
        return hash(self.__key)

    @property
    def labels(self) -> List[Tuple[str, Union[str, int]]]:
        return list(self.__labels.items())

    @property
    def key(self) -> str:
        return self.__key

    def get(self, label: str, default: Optional[str] = None) -> Union[str, int]:
        return self.__labels.get(label, default)

    def is_subset_of(self, other: 'StatName') -> bool:
        for k, v in self.__labels.items():
            if other.get(k, None) != v:
                return False

        return True

    def merge(self, other: 'StatName') -> 'StatName':
        labels = self.__labels.copy()
        labels.update(other.__labels)  # pylint: disable=protected-access
        return StatName(**labels)


class BaseStat(object):
    def __init__(self, name: StatName, registry: Registry, lock: threading.RLock) -> None:
        self.name = name
        self.registry = registry
        self._lock = lock

    def __str__(self) -> str:
        return '%s(%s)' % (self.__class__.__name__, self.name)
    __repr__ = __str__

    @property
    def key(self) -> str:
        return self.name.key

    @property
    def value(self) -> Union[int, float]:
        raise NotImplementedError

    def unregister(self) -> None:
        self.registry.unregister(self)
        self.registry = None


COUNTERVAL = TypeVar('COUNTERVAL', int, float)
class Counter(Generic[COUNTERVAL], BaseStat):
    def __init__(self, name: StatName, registry: Registry, lock: threading.RLock) -> None:
        super().__init__(name, registry, lock)

        self.__value = 0  # type: COUNTERVAL

    @property
    def value(self) -> Union[int, float]:
        return self.__value

    def incr(self, amount: COUNTERVAL = 1) -> None:
        with self._lock:
            self.__value += amount
