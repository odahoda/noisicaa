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


class ProcessManagerTest(unittest.AsyncTestCase):
    async def test_simple(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            def __init__(self, *, foo, **kwargs):
                super().__init__(**kwargs)
                assert foo == 'bar'

            async def run(self):
                pass

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_process('test', Child, foo='bar')
            await proc.wait()
            self.assertEqual(proc.returncode, 0)

    async def test_child_fails(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            async def run(self):
                os._exit(2)

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 2)

    async def test_child_killed(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            async def run(self):
                os.kill(self.pid, signal.SIGKILL)

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.signal, signal.SIGKILL)

    async def test_left_over(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            async def run(self):
                while True:
                    await asyncio.sleep(1)

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            stub = await mgr.start_process('test', Child)

    async def test_left_over_sigterm_fails(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            async def run(self):
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                while True:
                    await asyncio.sleep(1)

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            stub = await mgr.start_process('test', Child)
            await mgr.terminate_all_children(timeout=0.2)

    async def test_capture_stdout(self):
        class Child(process_manager.SubprocessMixin, process_manager.ProcessBase):
            async def run(self):
                for i in range(10):
                    print(i)
                sys.stderr.write('goo')

        async with process_manager.ProcessManager(self.loop, collect_stats=False) as mgr:
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 0)
