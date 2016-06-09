#!/usr/bin/python3

import asyncio
import os
import signal
import sys
# import time
import unittest

from . import process_manager


class ProcessManagerTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_simple(self):
        mgr = process_manager.ProcessManager(self.loop)
        mgr.start()

        class Child(process_manager.ProcessImpl):
            def run(self, foo):
                assert foo == 'bar'

        async def test_body():
            proc = await mgr.start_process('test', Child, 'bar')
            await proc.wait()
            self.assertEqual(proc.returncode, 0)
            
        self.loop.run_until_complete(test_body())

    def test_child_fails(self):
        mgr = process_manager.ProcessManager(self.loop)
        mgr.start()

        class Child(process_manager.ProcessImpl):
            def run(self):
                sys.exit(2)

        async def test_body():
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 2)
            
        self.loop.run_until_complete(test_body())

    def test_child_killed(self):
        mgr = process_manager.ProcessManager(self.loop)
        mgr.start()

        class Child(process_manager.ProcessImpl):
            def run(self):
                os.kill(self.pid, signal.SIGKILL)

        async def test_body():
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.signal, signal.SIGKILL)
            
        self.loop.run_until_complete(test_body())

    # def test_left_over(self):
    #     class Child(process_manager.ProcessImpl):
    #         def run(self):
    #             while True:
    #                 time.sleep(1)

    #     with process_manager.ProcessManager() as mgr:
    #         stub = mgr.start_process('test', Child)

    # def test_left_over_sigterm_fails(self):
    #     class Child(process_manager.ProcessImpl):
    #         def run(self):
    #             signal.signal(signal.SIGTERM, signal.SIG_IGN)
    #             while True:
    #                 time.sleep(1)

    #     with process_manager.ProcessManager() as mgr:
    #         stub = mgr.start_process('test', Child)
    #         mgr.terminate_all_children(timeout=0.2)

    def test_capture_stdout(self):
        mgr = process_manager.ProcessManager(self.loop)
        mgr.start()

        class Child(process_manager.ProcessImpl):
            def run(self):
                for i in range(10):
                    print(i)
                sys.stderr.write('goo')

        async def test_body():
            proc = await mgr.start_process('test', Child)
            await proc.wait()
            self.assertEqual(proc.returncode, 0)
            
        self.loop.run_until_complete(test_body())


if __name__ == '__main__':
    unittest.main()
