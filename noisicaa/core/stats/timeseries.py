#!/usr/bin/python3

import collections
import logging

logger = logging.getLogger(__name__)


class Value(object):
    def __init__(self, timestamp, value):
        assert isinstance(value, (int, float)), type(value)
        self.timestamp = timestamp
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(self.value)


class ValueSet(collections.UserDict):
    def __init__(self, data=None):
        super().__init__(data)

    def select(self, name):
        result = ValueSet()
        for value_name, value in self.data.items():
            if name.is_subset_of(value_name):
                result[value_name] = value

        return result


class Timeseries(collections.UserList):
    def __init__(self, values=None):
        super().__init__(values)

    def rate(self):
        result = Timeseries()
        prev_value = None
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

    def latest(self):
        return self.data[0]

    def max(self):
        return max(value.value for value in self)

    def min(self):
        return min(value.value for value in self)


class TimeseriesSet(collections.UserDict):
    def __init__(self, data=None):
        super().__init__(data)

    def select(self, name):
        result = TimeseriesSet()
        for ts_name, ts in self.data.items():
            if name.is_subset_of(ts_name):
                result[ts_name] = ts

        return result

    def rate(self):
        result = TimeseriesSet()
        for ts_name, ts in self.data.items():
            result[ts_name] = ts.rate()

        return result

    def latest(self):
        result = ValueSet()
        for ts_name, ts in self.data.items():
            result[ts_name] = ts.latest()

        return result

    def min(self):
        return min(ts.min() for ts in self.values())

    def max(self):
        return min(ts.max() for ts in self.values())
