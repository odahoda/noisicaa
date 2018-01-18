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

import itertools

from noisidev import unittest
from .time_mapper import PyTimeMapper
from .musical_time import PyMusicalTime, PyMusicalDuration


class TimeMapperTest(unittest.TestCase):
    def test_sample_to_musical_time(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()

            self.assertEqual(tmap.sample_to_musical_time(0), PyMusicalTime(0, 1))
            self.assertEqual(tmap.sample_to_musical_time(44100), PyMusicalTime(1, 2))
            self.assertEqual(tmap.sample_to_musical_time(88200), PyMusicalTime(1, 1))

        finally:
            tmap.cleanup()

    def test_musical_to_sample_time(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()

            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(0, 1)), 0)
            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(1, 2)), 44100)
            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(1, 1)), 88200)

        finally:
            tmap.cleanup()

    def test_bpm(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()
            self.assertEqual(tmap.bpm, 120)
            tmap.bpm = 240
            self.assertEqual(tmap.bpm, 240)

            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(0, 1)), 0)
            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(1, 2)), 22050)
            self.assertEqual(tmap.musical_to_sample_time(PyMusicalTime(1, 1)), 44100)

        finally:
            tmap.cleanup()

    def test_duration(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()
            self.assertEqual(tmap.duration, PyMusicalDuration(4, 1))
            tmap.duration = PyMusicalDuration(2, 1)
            self.assertEqual(tmap.duration, PyMusicalDuration(2, 1))
            self.assertEqual(tmap.end_time, PyMusicalTime(2, 1))
            self.assertEqual(tmap.num_samples, 176400)

        finally:
            tmap.cleanup()

    def test_iter(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()

            for stime, mtime in enumerate(itertools.islice(tmap, 20)):
                self.assertEqual(tmap.sample_to_musical_time(stime), mtime)

        finally:
            tmap.cleanup()

    def test_find(self):
        tmap = PyTimeMapper()
        try:
            tmap.setup()

            for stime, mtime in enumerate(
                    itertools.islice(tmap.find(PyMusicalTime(1, 2)), 20),
                    44100):
                self.assertEqual(tmap.sample_to_musical_time(stime), mtime)

        finally:
            tmap.cleanup()
