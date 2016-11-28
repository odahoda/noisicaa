#!/usr/bin/python3

import logging
import threading
import time

import psutil

from . import stats
from . import timeseries

logger = logging.getLogger(__name__)


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
                data.append((name, timeseries.Value(now, stat.value)))

            with proc_info.oneshot():
                cpu_times = proc_info.cpu_times()
                data.append((
                    stats.StatName(name='cpu_time', type='user'),
                    timeseries.Value(now, cpu_times.user)))
                data.append((
                    stats.StatName(name='cpu_time', type='system'),
                    timeseries.Value(now, cpu_times.system)))

                memory_info = proc_info.memory_info()
                data.append((
                    stats.StatName(name='memory', type='rss'),
                    timeseries.Value(now, memory_info.rss)))
                data.append((
                    stats.StatName(name='memory', type='vms'),
                    timeseries.Value(now, memory_info.vms)))

                io_counters = proc_info.io_counters()
                data.append((
                    stats.StatName(name='io', type='read_count'),
                    timeseries.Value(now, io_counters.read_count)))
                data.append((
                    stats.StatName(name='io', type='write_count'),
                    timeseries.Value(now, io_counters.write_count)))
                data.append((
                    stats.StatName(name='io', type='read_bytes'),
                    timeseries.Value(now, io_counters.read_bytes)))
                data.append((
                    stats.StatName(name='io', type='write_bytes'),
                    timeseries.Value(now, io_counters.write_bytes)))

                ctx_switches = proc_info.num_ctx_switches()
                data.append((
                    stats.StatName(name='ctx_switches', type='voluntary'),
                    timeseries.Value(now, ctx_switches.voluntary)))
                data.append((
                    stats.StatName(name='ctx_switches', type='involuntary'),
                    timeseries.Value(now, ctx_switches.involuntary)))

        return data
