#!/usr/bin/python3

import time
import unittest

from . import stats


class StatNameTest(unittest.TestCase):
    def test_key(self):
        self.assertEqual(stats.StatName(b=1, a=2).key, 'a=2:b=1')

    def test_is_subset_of(self):
        self.assertTrue(
            stats.StatName(a=1, b=2).is_subset_of(stats.StatName(a=1, b=2)))
        self.assertFalse(
            stats.StatName(a=1, b=2).is_subset_of(stats.StatName(a=1, b=3)))
        self.assertTrue(
            stats.StatName(a=1, b=2).is_subset_of(stats.StatName(a=1, b=2, c=3)))
        self.assertFalse(
            stats.StatName(a=1, b=2, c=3).is_subset_of(stats.StatName(a=1, b=2)))


class TimeseriesSetTest(unittest.TestCase):
    def test_select(self):
        s = stats.TimeseriesSet()
        ts1 = stats.Timeseries()
        s[stats.StatName(n=1)] = ts1
        ts2 = stats.Timeseries()
        s[stats.StatName(n=2)] = ts2

        r = s.select(n=1)
        self.assertEqual(len(r), 1)


class StatsTrackerTest(unittest.TestCase):
    def test_counter(self):
        tracker = stats.StatsTracker()
        tracker.get(stats.Counter, name='counter', l='one').incr()
        tracker.get(stats.Counter, name='counter', l='two').incr()

        self.assertEqual(
            tracker.get(stats.Counter, name='counter', l='one').value, 1)

        self.assertEqual(
            tracker.get(stats.Counter, name='counter', l='two').value, 1)

    def test_select(self):
        tracker = stats.StatsTracker()
        tracker.get(stats.Counter, name='counter', l='one')
        tracker.get(stats.Counter, name='counter', l='two')

        self.assertEqual(
            sorted([s.key for s in tracker.select()]),
            ['l=one:name=counter', 'l=two:name=counter'])

        self.assertEqual(
            sorted([s.key for s in tracker.select(l='one')]),
            ['l=one:name=counter'])

    def test_collect(self):
        tracker = stats.StatsTracker(timeseries_length=5)
        s1 = tracker.get(stats.Counter, name='s1')
        s2 = tracker.get(stats.Counter, name='s2')
        for _ in range(10):
            s1.incr()
            s2.incr(2)
            tracker.collect()

    def test_rule(self):
        tracker = stats.StatsTracker(timeseries_length=5)
        s1 = tracker.get(stats.Counter, name='s', l=1)
        s2 = tracker.get(stats.Counter, name='s', l=2)
        r = stats.Rule(stats.StatName(name='r'), lambda tsdata: tsdata.select(name='s').latest())
        tracker.add_rule(r)
        for _ in range(10):
            s1.incr()
            s2.incr(2)
            tracker.collect()

    def test_collection(self):
        tracker = stats.StatsTracker(collection_interval=100, timeseries_length=10)
        tracker.setup()
        try:
            s1 = tracker.get(stats.Counter, name='s1')
            s2 = tracker.get(stats.Counter, name='s2')
            for _ in range(10):
                s1.incr()
                s2.incr(2)
                time.sleep(0.1)
        finally:
            tracker.cleanup()

if __name__ == '__main__':
    unittest.main()
