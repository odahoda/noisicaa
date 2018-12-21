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

import collections
import logging
from typing import List, MutableMapping, MutableSequence, Union

from . import stats

logger = logging.getLogger(__name__)


ValueType = Union[int, float]


class Value(object):
    def __init__(self, timestamp: float, value: ValueType) -> None:
        assert isinstance(value, (int, float)), type(value)
        self.timestamp = timestamp
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return repr(self.value)


class ValueSet(collections.UserDict, MutableMapping[stats.StatName, Value]):
    def select(self, name: stats.StatName) -> 'ValueSet':
        result = ValueSet()
        for value_name, value in self.data.items():
            if name.is_subset_of(value_name):
                result[value_name] = value

        return result


class Timeseries(collections.UserList, MutableSequence[Value]):
    # Declaration for UserList in the typeshed does not include the data attribute.
    data = None  # type: List[Value]

    def rate(self) -> 'Timeseries':
        result = Timeseries()
        prev_value = None  # type: Value
        for value in reversed(self):
            if prev_value is not None:
                result.insert(
                    0,
                    Value(
                        value.timestamp,
                        (value.value - prev_value.value)
                        / (value.timestamp - prev_value.timestamp)))
            prev_value = value
        return result

    def latest(self) -> Value:
        return self.data[0]

    def max(self) -> ValueType:
        return max(value.value for value in self)

    def min(self) -> ValueType:
        return min(value.value for value in self)


class TimeseriesSet(collections.UserDict, MutableMapping[stats.StatName, Timeseries]):
    def select(self, name: stats.StatName) -> 'TimeseriesSet':
        result = TimeseriesSet()
        for ts_name, ts in self.data.items():
            if name.is_subset_of(ts_name):
                result[ts_name] = ts

        return result

    def rate(self) -> 'TimeseriesSet':
        result = TimeseriesSet()
        for ts_name, ts in self.data.items():
            result[ts_name] = ts.rate()

        return result

    def latest(self) -> ValueSet:
        result = ValueSet()
        for ts_name, ts in self.data.items():
            result[ts_name] = ts.latest()

        return result

    def min(self) -> ValueType:
        if self.data:
            return min(ts.min() for ts in self.values())
        else:
            return 0

    def max(self) -> ValueType:
        if self.data:
            return max(ts.max() for ts in self.values())
        else:
            return 0
