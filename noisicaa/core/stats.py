#!/usr/bin/python3

import collections
import logging
import pickle
import threading
import time
import pprint

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
        labels = self.__labels.copy()
        labels.update(other.__labels)
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


class Rule(object):
    def __init__(self, name, func):
        self.name = name
        self.__func = func

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)
    __repr__ = __str__

    @property
    def key(self):
        return self.name.key

    def evaluate(self, tsdata):
        return self.__func(tsdata)


class Value(object):
    def __init__(self, timestamp, value):
        self.timestamp = timestamp
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(self.value)


class ValueSet(collections.UserDict):
    def __init__(self, data=None):
        super().__init__(data)

    def select(self, **labels):
        name = StatName(**labels)

        result = ValueSet()
        for value_name, value in self.data.items():
            if name.is_subset_of(value_name):
                result[value_name] = value

        return result


class Timeseries(collections.UserList):
    def __init__(self, values=None):
        super().__init__(values)

    def latest(self):
        return self.data[0]


class TimeseriesSet(collections.UserDict):
    def __init__(self, data=None):
        super().__init__(data)

    def select(self, **labels):
        name = StatName(**labels)

        result = TimeseriesSet()
        for ts_name, ts in self.data.items():
            if name.is_subset_of(ts_name):
                result[ts_name] = ts

        return result

    def latest(self):
        result = ValueSet()
        for ts_name, ts in self.data.items():
            result[ts_name] = ts.latest()

        return result


class Registry(object):
    def __init__(self):
        self.__lock = threading.RLock()
        self.__stats = {}

    def register(self, stat_cls, name):
        with self.__lock:
            assert name not in self.__stats
            stat = stat_cls(name, self, self.__lock)
            self.__stats[name] = stat
            return stat

    def unregister(self, stat):
        with self.__lock:
            del self.__stats[stat.name]

    def collect(self):
        data = []
        with self.__lock:
            now = time.time()
            for name, stat in self.__stats.items():
                data.append((name, Value(now, stat.value)))

        return data


class Collector(object):
    def __init__(self, timeseries_length=60*10*10):
        self.__timeseries = TimeseriesSet()
        self.__rules = collections.OrderedDict()
        self.__timeseries_length = timeseries_length

    def add_value(self, name, value):
        ts = self.__timeseries.setdefault(name, Timeseries())
        ts.insert(0, value)

        drop_count = len(ts) - self.__timeseries_length
        if drop_count > 0:
            del ts[-drop_count:]

    def add_rule(self, rule):
        with self.__lock:
            assert rule.name not in self.__rules
            self.__rules[rule.name] = rule

    def collect(self, registry):
        for name, value in registry.collect():
            self.add_value(name, value)

    def evaluate_rules(self):
        now = time.time()
        for rule in self.__rules.values():
            value = rule.evaluate(self.__timeseries)
            if isinstance(value, (Timeseries, TimeseriesSet)):
                value = value.latest()

            if isinstance(value, Value):
                value = value.value

            if isinstance(value, ValueSet):
                for name, value in value.items():
                    rname = name.merge(rule.name)
                    self.add_value(rname, Value(now, value.value))

            elif isinstance(value, (int, float)):
                self.add_value(rule.name, Value(now, value))

    def dump(self):
        for name, ts in sorted(self.__timeseries.items()):
            logger.info("%s = %s", name, ts.latest())


registry = Registry()
