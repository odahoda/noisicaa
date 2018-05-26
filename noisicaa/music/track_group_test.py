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

import logging

from noisidev import unittest
from noisidev import unittest_mixins
from . import project
from . import track_group
from . import beat_track

logger = logging.getLogger(__name__)


class Signal(object):
    def __init__(self):
        self.__set = False

    def set(self):
        self.__set = True

    def clear(self):
        self.__set = False

    @property
    def is_set(self):
        return self.__set


class TrackGroupTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()
        self.project = self.pool.create(project.BaseProject, node_db=self.node_db)

    def test_duration_changed(self):
        duration_changed = Signal()
        self.project.master_group.listeners.add('duration_changed', duration_changed.set)

        logger.info("0 -------------")
        grp = self.pool.create(track_group.TrackGroup, name="group")
        self.project.master_group.tracks.append(grp)
        self.assertTrue(duration_changed.is_set)

        logger.info("1 -------------")
        duration_changed.clear()
        track = self.pool.create(beat_track.BeatTrack, name="track1")
        track.append_measure()
        track.append_measure()
        grp.tracks.append(track)
        self.assertTrue(duration_changed.is_set)

        logger.info("2 -------------")
        duration_changed.clear()
        track.append_measure()
        self.assertTrue(duration_changed.is_set)

        logger.info("3 -------------")
        duration_changed.clear()
        track.remove_measure(0)
        self.assertTrue(duration_changed.is_set)

        logger.info("4 -------------")
        duration_changed.clear()
        del self.project.master_group.tracks[track.index]
        self.assertTrue(duration_changed.is_set)
