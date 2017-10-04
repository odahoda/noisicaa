#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

        r = s.select(stats.StatName(n=1))
        self.assertEqual(len(r), 1)


class RegistryTest(unittest.TestCase):
    def test_counter(self):
        registry = stats.Registry()
        c1 = registry.register(stats.Counter, stats.StatName(name='counter', l='one'))
        c2 = registry.register(stats.Counter, stats.StatName(name='counter', l='two'))

        c1.incr()
        c2.incr()

        self.assertEqual(c1.value, 1)
        self.assertEqual(c2.value, 1)


class CollectorTest(unittest.TestCase):
    def test_collect(self):
        registry = stats.Registry()
        s1 = registry.register(stats.Counter, stats.StatName(name='s1'))
        s2 = registry.register(stats.Counter, stats.StatName(name='s2'))

        collector = stats.Collector(timeseries_length=5)
        for _ in range(10):
            s1.incr()
            s2.incr(2)
            collector.collect(registry)


if __name__ == '__main__':
    unittest.main()
