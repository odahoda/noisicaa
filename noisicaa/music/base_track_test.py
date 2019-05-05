#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
from typing import cast, Type

from noisidev import unittest_mixins
from . import base_track

logger = logging.getLogger(__name__)


class TrackTestMixin(unittest_mixins.ProjectMixin):
    node_uri = None  # type: str
    track_cls = None  # type: Type[base_track.Track]

    async def test_add_remove(self) -> None:
        with self.project.apply_mutations():
            node = self.project.create_node(self.node_uri)
        assert isinstance(node, self.track_cls)

        with self.project.apply_mutations():
            self.project.remove_node(node)

    async def _add_track(self) -> base_track.Track:
        with self.project.apply_mutations():
            return cast(base_track.Track, self.project.create_node(self.node_uri))
