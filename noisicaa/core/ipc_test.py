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
import io
import logging
import random
import sys
import time

import dbus
from indicator_cpufreq import cpufreq

from noisidev import unittest
from noisicaa.constants import TEST_OPTS
from . import process_manager
from . import empty_message_pb2
from . import ipc
from . import ipc_test_pb2

logger = logging.getLogger(__name__)


class IPCTest(unittest.AsyncTestCase):
    async def test_ping(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            await server.add_endpoint(ipc.ServerEndpoint('main'))
            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()
                await stub.ping()
                await stub.ping()

            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()

    async def test_good_message(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            async def handler(request, response):
                response.num = request.num + 1
            endpoint = ipc.ServerEndpoint('main')
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, server.address) as stub:
                request = ipc_test_pb2.TestRequest()
                request.num = 3
                response = ipc_test_pb2.TestResponse()
                await stub.call('foo', request, response)
                self.assertEqual(response.num, 4)

    async def test_endpoint(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            endpoint = ipc.ServerEndpoint('bar')

            async def handler(request, response):
                response.num = request.num + 1
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            endpoint_address = await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, endpoint_address) as stub:
                request = ipc_test_pb2.TestRequest()
                request.num = 3
                response = ipc_test_pb2.TestResponse()
                await stub.call('foo', request, response)
                self.assertEqual(response.num, 4)

    async def test_session(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            endpoint = ipc.ServerEndpointWithSessions('bar', ipc.Session)

            async def handler(session, request, response):
                self.assertIsInstance(session, ipc.Session)
                response.num = request.num + 1
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            endpoint_address = await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, endpoint_address) as stub:
                self.assertTrue(stub.session_id is not None)
                request = ipc_test_pb2.TestRequest()
                request.num = 3
                response = ipc_test_pb2.TestResponse()
                await stub.call('foo', request, response)
                self.assertEqual(response.num, 4)

    async def test_remote_exception(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            endpoint = ipc.ServerEndpoint('main')
            def handler(request, response):
                raise RuntimeError("boom")
            endpoint.add_handler(
                'foo', handler,
                ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')

    async def test_unknown_command(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            await server.add_endpoint(ipc.ServerEndpoint('main'))
            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')

    async def test_close_server(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            endpoint = ipc.ServerEndpoint('main')
            async def handler(request, response):
                self.loop.create_task(server.cleanup())
                await asyncio.sleep(0.1)
                response.num = request.num + 1
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, server.address) as stub:
                request = ipc_test_pb2.TestRequest()
                request.num = 3
                response = ipc_test_pb2.TestResponse()
                await stub.call('foo', request, response)
                self.assertEqual(response.num, 4)

    async def test_server_dies(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            endpoint = ipc.ServerEndpoint('main')
            async def handler(request, response):
                response.num = request.num + 1
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, server.address) as stub:
                request = ipc_test_pb2.TestRequest()
                request.num = 3
                response = ipc_test_pb2.TestResponse()
                await stub.call('foo', request, response)
                self.assertEqual(response.num, 4)

                await server.cleanup()

                with self.assertRaises(ipc.ConnectionClosed):
                    response = ipc_test_pb2.TestResponse()
                    await stub.call('foo', request, response)

    async def test_concurrent_requests(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            pending = [0]

            async def handler(request, response):
                pending[0] += 1
                while True:
                    if pending[0] > 3:
                        break
                    await asyncio.sleep(0.1)

                response.num = request.num + 1

            endpoint = ipc.ServerEndpoint('main')
            endpoint.add_handler(
                'foo', handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
            await server.add_endpoint(endpoint)

            async with ipc.Stub(self.loop, server.address) as stub:
                tasks = []
                responses = []
                for i in range(4):
                    request = ipc_test_pb2.TestRequest()
                    request.num = 3 + 2 * i
                    response = ipc_test_pb2.TestResponse()
                    tasks.append(self.loop.create_task(stub.call('foo', request, response)))
                    responses.append(response)

                done_tasks, pending_tasks = await asyncio.wait(tasks, timeout=5, loop=self.loop)
                self.assertEqual(len(done_tasks), 4)
                self.assertEqual(len(pending_tasks), 0)
                for task in tasks:
                    await task
                for i, response in enumerate(responses):
                    self.assertEqual(response.num, 4 + 2 * i)


class TestSubprocess(process_manager.SubprocessMixin, process_manager.ProcessBase):
    async def run(self):
        quit_event = asyncio.Event(loop=self.event_loop)

        endpoint = ipc.ServerEndpoint('main')
        endpoint.add_handler(
            'foo', self.msg_handler, ipc_test_pb2.TestRequest, ipc_test_pb2.TestResponse)
        endpoint.add_handler(
            'quit', lambda request, response: quit_event.set(),
            empty_message_pb2.EmptyMessage, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(endpoint)

        await quit_event.wait()

    async def msg_handler(self, request, response):
        response.num = 2


class IPCPerfTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.proxy = None
        self.old_governor = None
        self.mgr = None
        self.proc = None
        self.stub = None

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
        try:
            self.old_governor = cpufreq.get_policy(self.cpus[0])[2]
        except ValueError as exc:
            logger.error("Failed to query current CPU govenor: %s", exc)
            logger.error("Cannot set CPU to 'performance' for the perf tests.")
        else:
            self.bus = dbus.SystemBus()
            self.proxy = self.bus.get_object(
                'com.ubuntu.IndicatorCpufreqSelector', '/Selector', introspect=False)
            self.proxy.SetGovernor(
                self.cpus, 'performance', dbus_interface='com.ubuntu.IndicatorCpufreqSelector')

    async def cleanup_testcase(self):
        if self.old_governor is not None:
            self.proxy.SetGovernor(
                self.cpus, self.old_governor, dbus_interface='com.ubuntu.IndicatorCpufreqSelector')

        if self.stub is not None:
            await self.stub.call('quit')
            await self.stub.close()

        if self.proc is not None:
            await self.proc.wait()

        if self.mgr is not None:
            await self.mgr.cleanup()

    async def run_test(self, request, num_requests, *, out=sys.stdout):
        passes = []
        for _ in range(6):
            out.write('*')
            out.flush()
            wt0 = time.perf_counter()
            ct0 = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
            for _ in range(num_requests):
                response = ipc_test_pb2.TestResponse()
                await self.stub.call('foo', request, response)
            wt = time.perf_counter() - wt0
            ct = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID) - ct0
            passes.append((wt, ct))
        out.write('\n')

        passes = passes[1:]
        passes.sort()
        passes = passes[1:-1]
        wt = sum(t for t, _ in passes) / len(passes)
        ct = sum(t for _, t in passes) / len(passes)
        out.write(
            "\033[1mTotal: Wall time: \033[32m%.3fsec\033[37m  CPU time: \033[32m%.3fsec\033[37m\n"
            % (wt, ct))
        out.write("Per request: \033[32m%.2fµsec\033[37;0m\n" % (1e6 * wt / num_requests))

    async def test_smoke(self):
        # Not a real perf test, just execute the code during normal unit test runs to make sure it
        # doesn't bitrot.
        request = ipc_test_pb2.TestRequest()
        request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 10, out=io.StringIO())

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
