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

from noisidev import unittest
from . import perf_stats


class TestPerfStats(perf_stats.PyPerfStats):
    def __init__(self):
        super().__init__(self.get_time_nsec)
        self.fake_time = 0

    def get_time_nsec(self):
        return self.fake_time


class PerfStatsTest(unittest.TestCase):
    def test_track(self):
        pf = TestPerfStats()
        with pf.track('1'):
            pf.fake_time += 1
            with pf.track('2'):
                pf.fake_time += 1
            pf.fake_time += 1
            with pf.track('3'):
                pf.fake_time += 1
            pf.fake_time += 1

        self.assertEqual(pf.spans[0].name, '1')
        self.assertEqual(pf.spans[0].parent_id, 0)
        self.assertEqual(pf.spans[0].start_time_nsec, 0)
        self.assertEqual(pf.spans[0].end_time_nsec, 5)
        self.assertEqual(pf.spans[1].name, '2')
        self.assertEqual(pf.spans[1].parent_id, pf.spans[0].id)
        self.assertEqual(pf.spans[1].start_time_nsec, 1)
        self.assertEqual(pf.spans[1].end_time_nsec, 2)
        self.assertEqual(pf.spans[2].name, '3')
        self.assertEqual(pf.spans[2].parent_id, pf.spans[0].id)
        self.assertEqual(pf.spans[2].start_time_nsec, 3)
        self.assertEqual(pf.spans[2].end_time_nsec, 4)

    def test_track_with_parent(self):
        pf = TestPerfStats()
        with pf.track('1', 23):
            pf.fake_time += 1

        self.assertEqual(pf.spans[0].name, '1')
        self.assertEqual(pf.spans[0].parent_id, 23)
        self.assertEqual(pf.spans[0].start_time_nsec, 0)
        self.assertEqual(pf.spans[0].end_time_nsec, 1)

    def test_current_span_id(self):
        pf = TestPerfStats()
        self.assertEqual(pf.current_span_id, 0)
        with pf.track('1', 23):
            span_id = pf.current_span_id
            self.assertGreater(span_id, 0)
        self.assertEqual(pf.current_span_id, 0)
        self.assertEqual(span_id, pf.spans[0].id)

    def test_add_spans(self):
        pf1 = TestPerfStats()
        with pf1.track('1'):
            pf1.fake_time += 1

            pf2 = TestPerfStats()
            pf2.fake_time = pf1.fake_time
            with pf2.track('2'):
                pf2.fake_time += 1
            pf1.fake_time += 1
            pf1.add_spans(pf2)

        self.assertEqual(pf1.spans[0].name, '1')
        self.assertEqual(pf1.spans[0].parent_id, 0)
        self.assertEqual(pf1.spans[0].start_time_nsec, 0)
        self.assertEqual(pf1.spans[0].end_time_nsec, 2)
        self.assertEqual(pf1.spans[1].name, '2')
        self.assertEqual(pf1.spans[1].parent_id, pf1.spans[0].id)
        self.assertEqual(pf1.spans[1].start_time_nsec, 1)
        self.assertEqual(pf1.spans[1].end_time_nsec, 2)
