#!/usr/bin/python3

import unittest

from . import perf_stats

class TestPerfStats(perf_stats.PerfStats):
    def __init__(self):
        super().__init__()
        self.fake_time = 0

    def get_time_usec(self):
        return self.fake_time


class SpanTest(unittest.TestCase):
    def test_str(self):
        s = perf_stats.Span('1', 2)
        self.assertIsInstance(str(s), str)


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
        spans = pf.get_spans()

        self.assertEqual(spans[0].name, '1')
        self.assertEqual(spans[0].parent_id, 0)
        self.assertEqual(spans[0].start_time_nsec, 0)
        self.assertEqual(spans[0].end_time_nsec, 5)
        self.assertEqual(spans[1].name, '2')
        self.assertEqual(spans[1].parent_id, spans[0].id)
        self.assertEqual(spans[1].start_time_nsec, 1)
        self.assertEqual(spans[1].end_time_nsec, 2)
        self.assertEqual(spans[2].name, '3')
        self.assertEqual(spans[2].parent_id, spans[0].id)
        self.assertEqual(spans[2].start_time_nsec, 3)
        self.assertEqual(spans[2].end_time_nsec, 4)

    def test_track_with_parent(self):
        pf = TestPerfStats()
        with pf.track('1', 23):
            pf.fake_time += 1
        spans = pf.get_spans()

        self.assertEqual(spans[0].name, '1')
        self.assertEqual(spans[0].parent_id, 23)
        self.assertEqual(spans[0].start_time_nsec, 0)
        self.assertEqual(spans[0].end_time_nsec, 1)

    def test_current_span_id(self):
        pf = TestPerfStats()
        self.assertEqual(pf.current_span_id, 0)
        with pf.track('1', 23):
            span_id = pf.current_span_id
            self.assertGreater(span_id, 0)
        self.assertEqual(pf.current_span_id, 0)

        spans = pf.get_spans()
        self.assertEqual(span_id, spans[0].id)


if __name__ == '__main__':
    unittest.main()
