#!/usr/bin/python3

import os
import signal
import sys
import time
import unittest

from . import process_manager


class ProcessManagerTest(unittest.TestCase):
    def test_simple(self):
        class Child(process_manager.ProcessImpl):
            def run(self, foo):
                assert foo == 'bar'

        with process_manager.ProcessManager() as mgr:
            stub = mgr.start_process('test', Child, 'bar')
            stub.wait()
            self.assertEqual(stub.returncode, 0)

    def test_left_over(self):
        class Child(process_manager.ProcessImpl):
            def run(self):
                while True:
                    time.sleep(1)

        with process_manager.ProcessManager() as mgr:
            stub = mgr.start_process('test', Child)

    def test_left_over_sigterm_fails(self):
        class Child(process_manager.ProcessImpl):
            def run(self):
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                while True:
                    time.sleep(1)

        with process_manager.ProcessManager() as mgr:
            stub = mgr.start_process('test', Child)
            mgr.terminate_all_children(timeout=0.2)

    def test_capture_stdout(self):
        class Child(process_manager.ProcessImpl):
            def run(self):
                for i in range(10):
                    print(i)
                sys.stderr.write('goo')

        with process_manager.ProcessManager() as mgr:
            stub = mgr.start_process('test', Child)
            stub.wait()


if __name__ == '__main__':
    import logging
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
