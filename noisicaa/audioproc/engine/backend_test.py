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

# TODO: mypy-unclean

from noisidev import unittest
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from .buffers import PyFloatAudioBlock
from .realm import PyRealm
from .backend import PyBackend, PyBackendSettings
from .block_context import PyBlockContext


class BackendTest(unittest_engine_mixins.HostSystemMixin, unittest.TestCase):
    def test_output(self):
        realm = PyRealm(
            name='root', host_system=self.host_system,
            engine=None, parent=None, player=None)

        backend_settings = PyBackendSettings(time_scale=0)
        backend = PyBackend(self.host_system, 'null', backend_settings)
        backend.setup(realm)

        bufmgr = unittest_engine_utils.BufferManager(self.host_system)
        bufmgr.allocate('samples', PyFloatAudioBlock())
        samples = bufmgr['samples']

        ctxt = PyBlockContext()
        for _ in range(100):
            backend.begin_block(ctxt)

            for i in range(self.host_system.block_size):
                samples[i] = float(i) / self.host_system.block_size
            backend.output(ctxt, "left", samples)
            backend.output(ctxt, "right", samples)

            backend.end_block(ctxt)

        backend.cleanup()
