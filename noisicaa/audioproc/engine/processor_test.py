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

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisicaa import node_db
from . import processor


class ProcessorTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def test_id(self):
        node_description = node_db.NodeDescription(
            type=node_db.NodeDescription.PROCESSOR,
            ports=[],
            processor=node_db.ProcessorDescription(
                type='builtin://null',
            ),
        )

        proc1 = processor.PyProcessor('realm', 'test_node_1', self.host_system, node_description)
        proc2 = processor.PyProcessor('realm', 'test_node_2', self.host_system, node_description)

        self.assertNotEqual(proc1.id, proc2.id)
