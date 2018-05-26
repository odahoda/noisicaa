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

from noisicaa import model
from . import commands_pb2
from . import commands_test

logger = logging.getLogger(__name__)


class PropertiesTrackTest(commands_test.CommandsTestBase):
    async def test_set_time_signature(self):
        measure = self.project.property_track.measure_list[0].measure

        await self.client.send_command(commands_pb2.Command(
            target=self.project.property_track.id,
            set_time_signature=commands_pb2.SetTimeSignature(
                measure_ids=[measure.id],
                upper=3,
                lower=4)))
        self.assertEqual(measure.time_signature, model.TimeSignature(3, 4))
