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

import unittest

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

        msg = pf.serialize()
        self.assertEqual(msg.spans[0].name, '1')
        self.assertEqual(msg.spans[0].parentId, 0)
        self.assertEqual(msg.spans[0].startTimeNSec, 0)
        self.assertEqual(msg.spans[0].endTimeNSec, 5)
        self.assertEqual(msg.spans[1].name, '2')
        self.assertEqual(msg.spans[1].parentId, msg.spans[0].id)
        self.assertEqual(msg.spans[1].startTimeNSec, 1)
        self.assertEqual(msg.spans[1].endTimeNSec, 2)
        self.assertEqual(msg.spans[2].name, '3')
        self.assertEqual(msg.spans[2].parentId, msg.spans[0].id)
        self.assertEqual(msg.spans[2].startTimeNSec, 3)
        self.assertEqual(msg.spans[2].endTimeNSec, 4)

    def test_track_with_parent(self):
        pf = TestPerfStats()
        with pf.track('1', 23):
            pf.fake_time += 1

        msg = pf.serialize()
        self.assertEqual(msg.spans[0].name, '1')
        self.assertEqual(msg.spans[0].parentId, 23)
        self.assertEqual(msg.spans[0].startTimeNSec, 0)
        self.assertEqual(msg.spans[0].endTimeNSec, 1)

    def test_current_span_id(self):
        pf = TestPerfStats()
        self.assertEqual(pf.current_span_id, 0)
        with pf.track('1', 23):
            span_id = pf.current_span_id
            self.assertGreater(span_id, 0)
        self.assertEqual(pf.current_span_id, 0)

        msg = pf.serialize()
        self.assertEqual(span_id, msg.spans[0].id)

    def test_add_spans(self):
        pf1 = TestPerfStats()
        with pf1.track('1'):
            pf1.fake_time += 1

            pf2 = TestPerfStats()
            pf2.fake_time = pf1.fake_time
            with pf2.track('2'):
                pf2.fake_time += 1
            pf1.fake_time += 1
            pf1.add_spans(pf2.serialize())


        msg = pf1.serialize()
        self.assertEqual(msg.spans[0].name, '1')
        self.assertEqual(msg.spans[0].parentId, 0)
        self.assertEqual(msg.spans[0].startTimeNSec, 0)
        self.assertEqual(msg.spans[0].endTimeNSec, 2)
        self.assertEqual(msg.spans[1].name, '2')
        self.assertEqual(msg.spans[1].parentId, msg.spans[0].id)
        self.assertEqual(msg.spans[1].startTimeNSec, 1)
        self.assertEqual(msg.spans[1].endTimeNSec, 2)



if __name__ == '__main__':
    unittest.main()
