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

from noisidev import unittest
from noisicaa.constants import TEST_OPTS
from noisicaa import core
from noisicaa.core import ipc
from . import urid_mapper

logger = logging.getLogger(__name__)


class DynamicURIDMapperTest(unittest.TestCase):
    def test_map(self):
        mapper = urid_mapper.PyDynamicURIDMapper()

        urid = mapper.map('http://www.odahoda.de/')
        self.assertIsInstance(urid, int)
        self.assertGreater(urid, 0)

        uri = mapper.unmap(urid)
        self.assertEqual(uri, 'http://www.odahoda.de/')

    def test_unmap_unknown(self):
        mapper = urid_mapper.PyDynamicURIDMapper()
        self.assertIsNone(mapper.unmap(1102020))

    def test_known(self):
        mapper = urid_mapper.PyDynamicURIDMapper()

        self.assertFalse(mapper.known('http://www.odahoda.de/'))
        mapper.map('http://www.odahoda.de/')
        self.assertTrue(mapper.known('http://www.odahoda.de/'))

    def test_list(self):
        mapper = urid_mapper.PyDynamicURIDMapper()
        l = list(mapper.list())
        self.assertEqual(l, [])

        mapper.map('http://www.odahoda.de/foo')
        mapper.map('http://www.odahoda.de/bar')
        l = list(mapper.list())
        self.assertEqual(len(l), 2)
        self.assertEqual(
            {uri for uri, _ in l},
            {'http://www.odahoda.de/foo', 'http://www.odahoda.de/bar'})
        self.assertEqual(len({urid for _, urid in l}), 2)


class ProxyURIDMapperTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mgr = None
        self.proc = None

    async def setup_testcase(self):
        self.mgr = core.ProcessManager(event_loop=self.loop)
        await self.mgr.setup()

        self.proc = await self.mgr.start_subprocess(
            'test-urid-mapper', 'noisicaa.lv2.urid_mapper_process.URIDMapperSubprocess')

    async def cleanup_testcase(self):
        if self.proc:
            stub = ipc.Stub(self.loop, self.proc.address)
            await stub.connect()
            await stub.call('SHUTDOWN')
            await stub.close()
            await self.proc.wait()

        if self.mgr is not None:
            await self.mgr.cleanup()

    async def test_map(self):
        mapper = urid_mapper.PyProxyURIDMapper(
            tmp_dir=TEST_OPTS.TMP_DIR,
            server_address=self.proc.address)
        try:
            await mapper.setup(self.loop)

            urid = mapper.map('http://www.odahoda.de/')
            self.assertIsInstance(urid, int)
            self.assertGreater(urid, 0)

            self.assertEqual(mapper.map('http://www.odahoda.de/'), urid)
            self.assertEqual(mapper.unmap(urid), 'http://www.odahoda.de/')

        finally:
            await mapper.cleanup(self.loop)

    async def test_concurrent_map(self):
        mapper1 = urid_mapper.PyProxyURIDMapper(
            tmp_dir=TEST_OPTS.TMP_DIR,
            server_address=self.proc.address)
        mapper2 = urid_mapper.PyProxyURIDMapper(
            tmp_dir=TEST_OPTS.TMP_DIR,
            server_address=self.proc.address)
        try:
            await mapper1.setup(self.loop)
            urid1 = mapper1.map('http://www.odahoda.de/1')

            await mapper2.setup(self.loop)
            self.assertEqual(mapper2.unmap(urid1), 'http://www.odahoda.de/1')
            self.assertEqual(mapper2.map('http://www.odahoda.de/1'), urid1)

            urid2 = mapper2.map('http://www.odahoda.de/2')

            self.assertEqual(mapper1.unmap(urid2), 'http://www.odahoda.de/2')
            self.assertEqual(mapper1.map('http://www.odahoda.de/2'), urid2)

        finally:
            await mapper1.cleanup(self.loop)
            await mapper2.cleanup(self.loop)
