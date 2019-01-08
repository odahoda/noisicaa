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

from typing import List

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa import audioproc
from noisicaa.music import project
from noisicaa.music import pmodel_test
from . import server_impl
from . import processor_messages


class ControlTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()
        self.node = self.pool.create(server_impl.CustomCSound, name='test')
        self.messages = []  # type: List[audioproc.ProcessorMessage]

    def message_cb(self, msg):
        self.messages.append(msg)

    def test_messages_on_mutations(self):
        connector = self.node.create_node_connector(message_cb=self.message_cb)
        try:
            self.assertEqual(
                connector.init(),
                [processor_messages.set_script(self.node.pipeline_node_id, '', '')])

            self.messages.clear()
            self.node.orchestra = 'orch'
            self.assertEqual(
                self.messages,
                [processor_messages.set_script(self.node.pipeline_node_id, 'orch', '')])

            self.messages.clear()
            self.node.score = 'scr'
            self.assertEqual(
                self.messages,
                [processor_messages.set_script(self.node.pipeline_node_id, 'orch', 'scr')])

        finally:
            connector.close()


class CustomCSoundTest(pmodel_test.BasePipelineGraphNodeMixin, pmodel_test.ModelTest):
    cls = server_impl.CustomCSound
    create_args = {'name': 'test'}

    def test_orchestra(self):
        node = self.pool.create(self.cls, **self.create_args)

        node.orchestra = 'blabla'
        self.assertEqual(node.orchestra, 'blabla')

    def test_score(self):
        node = self.pool.create(self.cls, **self.create_args)

        node.score = 'blabla'
        self.assertEqual(node.score, 'blabla')
