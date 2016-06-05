#!/usr/bin/python3

import time
import unittest

from noisicaa import core
from noisicaa.core import ipc

from . import project_process
from . import project_stub


class ProjectProcessTest(unittest.TestCase):
    def test_start_and_shutdown(self):
        with core.ProcessManager() as mgr:
            proc = mgr.start_process(
                'test', project_process.ProjectProcess)
            with project_stub.ProjectStub(proc.address) as stub:
                stub.shutdown()
            proc.wait()

    def test_getprop(self):
        with core.ProcessManager() as mgr:
            proc = mgr.start_process(
                'test', project_process.ProjectProcess)
            with project_stub.ProjectStub(proc.address) as stub:
                self.assertEqual(
                    stub.get_property('/', 'current_sheet'), 0)
                stub.shutdown()
            proc.wait()


if __name__ == '__main__':
    unittest.main()
