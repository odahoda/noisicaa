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

from typing import cast

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.audioproc.public import instrument_spec_pb2
from . import model
from . import processor_messages


class InstrumentTest(
        unittest_mixins.NodeConnectorMixin,
        unittest_mixins.ProjectMixin,
        unittest.AsyncTestCase):
    async def _add_node(self) -> model.Instrument:
        with self.project.apply_mutations():
            return cast(
                model.Instrument,
                self.project.create_node('builtin://instrument'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.Instrument)

    async def test_connector_init(self):
        node = await self._add_node()
        with self.connector(node) as initial_messages:
            self.assertEqual(initial_messages, [])

    async def test_change_instrument_uri(self):
        node = await self._add_node()
        with self.connector(node):
            with self.project.apply_mutations():
                node.instrument_uri = 'sf2:/test.sf2?bank=2&preset=4'

            self.assertEqual(
                self.messages,
                [processor_messages.change_instrument(
                    node.pipeline_node_id,
                    instrument_spec_pb2.InstrumentSpec(
                        sf2=instrument_spec_pb2.SF2InstrumentSpec(
                            path='/test.sf2',
                            bank=2,
                            preset=4)))])
