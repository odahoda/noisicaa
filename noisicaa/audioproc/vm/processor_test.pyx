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

from libcpp.memory cimport unique_ptr

import unittest

from noisicaa.core.status cimport *
from .processor cimport *
from .host_data cimport *


class TestProcessor(unittest.TestCase):
    def test_id(self):
        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'null')
        check(stor_processor)
        cdef unique_ptr[Processor] processor1
        processor1.reset(stor_processor.result())

        stor_processor = Processor.create(
            b'test_node', host_data.get(), b'null')
        cdef unique_ptr[Processor] processor2
        processor2.reset(stor_processor.result())

        self.assertNotEqual(processor1.get().id(), processor2.get().id())
