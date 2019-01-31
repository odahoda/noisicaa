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

import asyncio
import random
import sys
import time

import dbus
from indicator_cpufreq import cpufreq

from noisidev import unittest
from noisicaa.constants import TEST_OPTS
from . import process_manager
from . import ipc
from . import ipc_test_pb2


class IPCTest(unittest.AsyncTestCase):
    async def test_ping(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()
                await stub.ping()
                await stub.ping()

            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()

    async def test_command(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            server.add_command_handler('foo', lambda: None)
            server.add_command_handler('bar', lambda: 'yo')
            server.add_command_handler('gnurz', lambda a: a + 1)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertIsNone(await stub.call('foo'))
                self.assertEqual(await stub.call('bar'), 'yo')
                self.assertEqual(await stub.call('gnurz', 3), 4)

    async def test_remote_exception(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            server.add_command_handler('foo', lambda: 1/0)
            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')

    async def test_async_handler(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            async def handler(arg):
                return arg + 1
            server.add_command_handler('foo', handler)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertEqual(await stub.call('foo', 3), 4)


class TestSubprocess(process_manager.SubprocessMixin, process_manager.ProcessBase):
    async def run(self):
        quit_event = asyncio.Event(loop=self.event_loop)

        self.server.add_command_handler('foo', self.msg_handler)
        self.server.add_command_handler('quit', quit_event.set)
        await quit_event.wait()

    async def msg_handler(self, msg):
        return ipc_test_pb2.TestResponse(num=2)


class IPCPerfTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.mgr = process_manager.ProcessManager(self.loop, collect_stats=False)
        await self.mgr.setup()
        self.proc = await self.mgr.start_subprocess(
            'test', 'noisicaa.core.ipc_test.TestSubprocess')

        self.stub = ipc.Stub(self.loop, self.proc.address)
        await self.stub.connect()

        # Set CPUs to performance mode, so test results are not skewed by variable CPU frequency.
        maxcpu = 0
        while cpufreq.cpu_exists(maxcpu) == 0:
            maxcpu += 1
        self.cpus = [dbus.UInt32(cpu) for cpu in range(maxcpu)]
        self.old_governor = cpufreq.get_policy(self.cpus[0])[2]
        self.bus = dbus.SystemBus()
        self.proxy = self.bus.get_object(
            'com.ubuntu.IndicatorCpufreqSelector', '/Selector', introspect=False)
        self.proxy.SetGovernor(
            self.cpus, 'performance', dbus_interface='com.ubuntu.IndicatorCpufreqSelector')

    async def cleanup_testcase(self):
        self.proxy.SetGovernor(
            self.cpus, self.old_governor, dbus_interface='com.ubuntu.IndicatorCpufreqSelector')

        await self.stub.call('quit')
        await self.stub.close()
        await self.proc.wait()
        await self.mgr.cleanup()

    async def run_test(self, request, num_requests):
        passes = []
        for _ in range(6):
            sys.stdout.write('*')
            sys.stdout.flush()
            wt0 = time.perf_counter()
            ct0 = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
            for _ in range(num_requests):
                await self.stub.call('foo', request)
            wt = time.perf_counter() - wt0
            ct = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID) - ct0
            passes.append((wt, ct))
        sys.stdout.write('\n')

        passes = passes[1:]
        passes.sort()
        passes = passes[1:-1]
        wt = sum(t for t, _ in passes) / len(passes)
        ct = sum(t for _, t in passes) / len(passes)
        sys.stdout.write(
            "\033[1mTotal: Wall time: \033[32m%.3fsec\033[37m  CPU time: \033[32m%.3fsec\033[37m\n"
            % (wt, ct))
        sys.stdout.write("Per request: \033[32m%.2fµsec\033[37;0m\n" % (1e6 * wt / num_requests))

    async def test_smoke(self):
        # Not a real perf test, just execute the code during normal unit test runs to make sure it
        # doesn't bitrot.
        request = ipc_test_pb2.TestRequest()
        request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 10)

    @unittest.tag('perf')
    async def test_small_messages(self):
        request = ipc_test_pb2.TestRequest()
        request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 5000)

    @unittest.tag('perf')
    async def test_large_messages(self):
        request = ipc_test_pb2.TestRequest()
        for _ in range(10000):
            request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 100)
