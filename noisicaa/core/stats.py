#!/usr/bin/python3

import collections
import logging
import threading
import time

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
    def __init__(self, name, tracker, lock):
        self.name = name
        self.tracker = tracker
        self._lock = lock

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)
    __repr__ = __str__

    @property
    def key(self):
        return self.name.key

    def unregister(self):
        self.tracker.unregister(self)
        self.tracker = None


class Counter(BaseStat):
    def __init__(self, name, tracker, lock):
        super().__init__(name, tracker, lock)

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


class StatsTracker(object):
    def __init__(self, collection_interval=100, timeseries_length=60*10*10):
        self.__lock = threading.RLock()
        self.__stats = {}
        self.__timeseries = TimeseriesSet()
        self.__rules = collections.OrderedDict()

        self.__collection_interval = collection_interval
        self.__timeseries_length = timeseries_length
        self.__collector_thread = None
        self.__stop_collector_thread = None

    def setup(self):
        assert self.__collector_thread is None
        self.__stop_collector_thread = threading.Event()
        self.__collector_thread = threading.Thread(target=self.__collector_main)
        self.__collector_thread.start()

    def cleanup(self):
        if self.__collector_thread is not None:
            self.__stop_collector_thread.set()
            self.__collector_thread.join()
            self.__collector_thread = None
            self.__stop_collector_thread = None

    def __collector_main(self):
        next_collection = time.perf_counter()
        while not self.__stop_collector_thread.is_set():
            delay = next_collection - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

            self.collect()
            next_collection += self.__collection_interval / 1e3

    def register(self, stat_cls, name):
        with self.__lock:
            assert name not in self.__stats
            stat = stat_cls(name, self, self.__lock)
            self.__stats[name] = stat
            return stat

    def unregister(self, stat):
        with self.__lock:
            del self.__stats[stat.name]

    def get(self, stat_cls, **labels):
        with self.__lock:
            stat_name = StatName(**labels)
            try:
                stat = self.__stats[stat_name]
                assert isinstance(stat, stat_cls)
            except KeyError:
                stat = stat_cls(stat_name, self.__lock)
                self.__stats[stat_name] = stat
        return stat

    def add_rule(self, rule):
        with self.__lock:
            assert rule.name not in self.__rules
            self.__rules[rule.name] = rule

    def select(self, **labels):
        with self.__lock:
            stat_name = StatName(**labels)
            for stat in self.__stats.values():
                if stat_name.is_subset_of(stat.name):
                    yield stat

    def collect(self):
        with self.__lock:
            now = time.time()
            for stat in self.__stats.values():
                ts = self.__timeseries.setdefault(stat.name, Timeseries())
                ts.insert(0, Value(now, stat.value))

                drop_count = len(ts) - self.__timeseries_length
                if drop_count > 0:
                    del ts[-drop_count:]

            for rule in self.__rules.values():
                value = rule.evaluate(self.__timeseries)
                if isinstance(value, (Timeseries, TimeseriesSet)):
                    value = value.latest()

                if isinstance(value, Value):
                    value = value.value

                if isinstance(value, ValueSet):
                    for name, value in value.items():
                        rname = name.merge(rule.name)
                        ts = self.__timeseries.setdefault(rname, Timeseries())
                        ts.insert(0, Value(now, value.value))
                        drop_count = len(ts) - self.__timeseries_length
                        if drop_count > 0:
                            del ts[-drop_count:]

                elif isinstance(value, (int, float)):
                    ts = self.__timeseries.setdefault(rule.name, Timeseries())
                    ts.insert(0, Value(now, value))
                    drop_count = len(ts) - self.__timeseries_length
                    if drop_count > 0:
                        del ts[-drop_count:]

            #print(self.__timeseries)


tracker = StatsTracker()
