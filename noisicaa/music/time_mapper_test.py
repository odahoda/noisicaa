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

import unittest

from . import project
from . import time_mapper
from . import time_signature


class TimeMapperTest(unittest.TestCase):
    def setUp(self):
        self.project = project.BaseProject()

        assert len(self.project.property_track.measure_list) == 1
        assert self.project.bpm == 120
        assert self.project.property_track.measure_list[0].measure.time_signature == time_signature.TimeSignature(4, 4)

    def test_total_duration(self):
        conv = time_mapper.TimeMapper(self.project)
        self.project.property_track.append_measure()
        self.project.property_track.append_measure()
        self.project.property_track.measure_list[1].measure.time_signature = time_signature.TimeSignature(2, 4)

        self.assertEqual(conv.total_duration_ticks, 480 + 240 + 480)
        self.assertEqual(conv.total_duration_samples, 88200 + 44100 + 88200)

    def test_time_out_of_range(self):
        conv = time_mapper.TimeMapper(self.project)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.sample2tick(-1)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.sample2tick(100000)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.tick2sample(-1)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.tick2sample(100000)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.measure_pos(-1)
        with self.assertRaises(time_mapper.TimeOutOfRange):
            conv.measure_pos(100000)

    def test_tick2sample(self):
        conv = time_mapper.TimeMapper(self.project)
        self.project.property_track.append_measure()

        self.assertEqual(conv.tick2sample(0), 0)
        self.assertEqual(conv.tick2sample(240), 44100)
        self.assertEqual(conv.tick2sample(480), 88200)
        self.assertEqual(conv.tick2sample(720), 132300)
        self.assertEqual(conv.tick2sample(960), 176400)

    def test_sample2tick(self):
        conv = time_mapper.TimeMapper(self.project)
        self.project.property_track.append_measure()

        self.assertEqual(conv.sample2tick(0), 0)
        self.assertEqual(conv.sample2tick(44100), 240)
        self.assertEqual(conv.sample2tick(88200), 480)
        self.assertEqual(conv.sample2tick(132300), 720)
        self.assertEqual(conv.sample2tick(176400), 960)

    def test_measure_pos(self):
        conv = time_mapper.TimeMapper(self.project)
        self.project.property_track.append_measure()
        self.project.property_track.append_measure()
        self.project.property_track.measure_list[1].measure.time_signature = time_signature.TimeSignature(2, 4)

        self.assertEqual(conv.measure_pos(0), (0, 0))
        self.assertEqual(conv.measure_pos(240), (0, 240))
        self.assertEqual(conv.measure_pos(479), (0, 479))
        self.assertEqual(conv.measure_pos(480), (1, 0))
        self.assertEqual(conv.measure_pos(600), (1, 120))
        self.assertEqual(conv.measure_pos(719), (1, 239))
        self.assertEqual(conv.measure_pos(720), (2, 0))
        self.assertEqual(conv.measure_pos(960), (2, 240))
        self.assertEqual(conv.measure_pos(1199), (2, 479))
        self.assertEqual(conv.measure_pos(1200), (3, 0))

if __name__ == '__main__':
    unittest.main()
