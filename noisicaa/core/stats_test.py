#!/usr/bin/python3

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


class StatsTest(unittest.TestCase):
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
            [s.key for s in tracker.select()],
            ['l=one:name=counter', 'l=two:name=counter'])


if __name__ == '__main__':
    unittest.main()
