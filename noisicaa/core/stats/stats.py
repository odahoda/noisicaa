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

logger = logging.getLogger(__name__)


class StatName(object):
    def __init__(self, **labels):
        self.__labels = labels

        self.__key = ':'.join(
            '%s=%s' % (k, v)
            for k, v in sorted(self.__labels.items()))

    def __str__(self):
        return self.__key
    __repr__ = __str__

    def __lt__(self, other):
        return self.key < other.key

    def __eq__(self, other):
        return self.key == other.key

    def __hash__(self):
        return hash(self.__key)

    @property
    def labels(self):
        return list(self.__labels.items())

    @property
    def key(self):
        return self.__key

    def get(self, label, default=None):
        return self.__labels.get(label, default)

    def is_subset_of(self, other):
        for k, v in self.__labels.items():
            if other.get(k, None) != v:
                return False

        return True

    def merge(self, other):
        assert isinstance(other, StatName)
        labels = self.__labels.copy()
        labels.update(other.__labels)  # pylint: disable=protected-access
        return StatName(**labels)


class BaseStat(object):
    def __init__(self, name, registry, lock):
        self.name = name
        self.registry = registry
        self._lock = lock

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)
    __repr__ = __str__

    @property
    def key(self):
        return self.name.key

    def unregister(self):
        self.registry.unregister(self)
        self.registry = None


class Counter(BaseStat):
    def __init__(self, name, registry, lock):
        super().__init__(name, registry, lock)

        self.__value = 0

    @property
    def value(self):
        return self.__value

    def incr(self, amount=1):
        with self._lock:
            self.__value += amount
