#!/usr/bin/python3

import collections
import logging
import pickle
import threading
import time
import pprint

import psutil

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

    def rate(self):
        result = Timeseries()
        prev_value = None
        for value in reversed(self):
            if prev_value is not None:
                result.insert(0, Value(value.timestamp, (value.value - prev_value.value) / (value.timestamp - prev_value.timestamp)))
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

    def clear(self):
        with self.__lock:
            for stat in list(self.__stats.values()):
                stat.unregister()
            assert not self.__stats

    def collect(self):
        data = []
        proc_info = psutil.Process()

        with self.__lock:
            now = time.time()
            for name, stat in self.__stats.items():
                data.append((name, Value(now, stat.value)))

            with proc_info.oneshot():
                cpu_times = proc_info.cpu_times()
                data.append((
                    StatName(name='cpu_time', type='user'),
                    Value(now, cpu_times.user)))
                data.append((
                    StatName(name='cpu_time', type='system'),
                    Value(now, cpu_times.system)))

                memory_info = proc_info.memory_info()
                data.append((
                    StatName(name='memory', type='rss'),
                    Value(now, memory_info.rss)))
                data.append((
                    StatName(name='memory', type='vms'),
                    Value(now, memory_info.vms)))

                io_counters = proc_info.io_counters()
                data.append((
                    StatName(name='io', type='read_count'),
                    Value(now, io_counters.read_count)))
                data.append((
                    StatName(name='io', type='write_count'),
                    Value(now, io_counters.write_count)))
                data.append((
                    StatName(name='io', type='read_bytes'),
                    Value(now, io_counters.read_bytes)))
                data.append((
                    StatName(name='io', type='write_bytes'),
                    Value(now, io_counters.write_bytes)))

                ctx_switches = proc_info.num_ctx_switches()
                data.append((
                    StatName(name='ctx_switches', type='voluntary'),
                    Value(now, ctx_switches.voluntary)))
                data.append((
                    StatName(name='ctx_switches', type='involuntary'),
                    Value(now, ctx_switches.involuntary)))

        return data


class Collector(object):
    def __init__(self, timeseries_length=60*10*10):
        self.__timeseries = TimeseriesSet()
        self.__timeseries_length = timeseries_length

    def add_value(self, name, value):
        ts = self.__timeseries.setdefault(name, Timeseries())
        ts.insert(0, value)

        drop_count = len(ts) - self.__timeseries_length
        if drop_count > 0:
            del ts[-drop_count:]

    def collect(self, registry):
        for name, value in registry.collect():
            self.add_value(name, value)

    def evaluate_expression(self, expr):
        result = self.__timeseries

        for op, *args in expr:
            if op == 'SELECT':
                result = result.select(args[0])
            elif op == 'RATE':
                result = result.rate()
            else:
                raise ValueError(op)

        return result

    def list_stats(self):
        return list(sorted(self.__timeseries.keys()))

    def fetch_stats(self, expressions):
        return {
            id: self.evaluate_expression(expr)
            for id, expr in expressions.items()}

    def dump(self):
        for name, ts in sorted(self.__timeseries.items()):
            logger.info("%s = %s", name, ts.latest())


registry = Registry()
