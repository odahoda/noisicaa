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

# TODO: pylint-unclean

import asyncio
import os
import signal
import sys

from noisidev import unittest
from . import process_manager


class TestProcess(process_manager.ProcessBase):
    def __init__(self, *, action, **kwargs):
        super().__init__(**kwargs)

        self.__action = action

    async def run(self):
        if self.__action == 'success':
            pass

        elif self.__action == 'fail':
            return 2

        elif self.__action == 'fail_hard':
            os._exit(2)

        elif self.__action == 'kill':
            os.kill(self.pid, signal.SIGKILL)

        elif self.__action == 'loop':
            while True:
                await asyncio.sleep(1, loop=self.event_loop)

        elif self.__action == 'loop_no_sigterm':
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            while True:
                await asyncio.sleep(1, loop=self.event_loop)

        elif self.__action == 'print':
            for i in range(10):
                print(i)
            sys.stderr.write('goo')

        else:
            raise ValueError(self.__action)


class TestSubprocess(process_manager.SubprocessMixin, TestProcess):
    pass


class SubprocessTest(unittest.AsyncTestCase):
    async def test_simple(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='success')
            await proc.wait()
            self.assertEqual(proc.returncode, 0)

    async def test_child_fails(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='fail_hard')
            await proc.wait()
            self.assertEqual(proc.returncode, 2)

    async def test_child_killed(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='kill')
            await proc.wait()
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.signal, signal.SIGKILL)

    async def test_left_over(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            stub = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='loop')

    async def test_left_over_sigterm_fails(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            stub = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='loop_no_sigterm')
            await mgr.terminate_all_children(timeout=0.2)

    async def test_capture_stdout(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_subprocess(
                'test', 'noisicaa.core.process_manager_test.TestSubprocess', action='print')
            await proc.wait()
            self.assertEqual(proc.returncode, 0)


class InlineProcessTest(unittest.AsyncTestCase):
    async def test_simple(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_inline_process(
                'test', 'noisicaa.core.process_manager_test.TestProcess', action='success')
            await proc.wait()
            self.assertEqual(proc.returncode, 0)

    async def test_child_fails(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_inline_process(
                'test', 'noisicaa.core.process_manager_test.TestProcess', action='fail')
            await proc.wait()
            self.assertEqual(proc.returncode, 2)

    async def test_left_over(self):
        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            stub = await mgr.start_inline_process(
                'test', 'noisicaa.core.process_manager_test.TestProcess', action='loop')
