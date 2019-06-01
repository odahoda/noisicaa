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

import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore

from noisidev import uitest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from . import project_registry


class ProjectRegistryTest(
        unittest_mixins.NodeDBMixin,
        unittest_mixins.URIDMapperMixin,
        unittest_mixins.ServerMixin,
        uitest.UITestCase):
    async def test_foo(self):
        registry = project_registry.ProjectRegistry(
            event_loop=self.loop,
            tmp_dir=TEST_OPTS.TMP_DIR,
            server=self.server,
            process_manager=self.process_manager_client,
            node_db=self.node_db,
            urid_mapper=self.urid_mapper,
        )
        await registry.setup()
        await registry.cleanup()
