#!/usr/bin/python3

import collections
import logging

logger = logging.getLogger(__name__)


class StatName(collections.UserDict):
    def __init__(self, **labels):
        super().__init__(labels)

        self.__key = ':'.join(
            '%s=%s' % (k, v)
            for k, v in sorted(self.data.items()))

    @property
    def key(self):
        return self.__key

    def is_subset_of(self, other):
        for k, v in self.data.items():
            if other.get(k, None) != v:
                return False

        return True


class BaseStat(object):
    def __init__(self, name):
        self.name = name

    @property
    def key(self):
        return self.name.key


class Counter(BaseStat):
    def __init__(self, name):
        super().__init__(name)

        self.__value = 0

    @property
    def value(self):
        return self.__value

    def incr(self, amount=1):
        self.__value += amount


class StatsTracker(object):
    def __init__(self):
        self.__stats = {}

    def get(self, stat_cls, **labels):
        stat_name = StatName(**labels)
        try:
            stat = self.__stats[stat_name.key]
            assert isinstance(stat, stat_cls)
        except KeyError:
            stat = stat_cls(stat_name)
            self.__stats[stat_name.key] = stat
        return stat

    def select(self, **labels):
        stat_name = StatName(**labels)
        for name, stat in self.__stats.items():
            if stat_name.is_subset_of(name):
                yield stat


