#!/usr/bin/python3

import time
import unittest

from noisicaa import core
from noisicaa.core import ipc

from . import project_process


class ProjectProcessTest(unittest.TestCase):
    def test_start_and_shutdown(self):
        with core.ProcessManager() as mgr:
            proc = mgr.start_process(
                'test', project_process.ProjectProcess)
            with ipc.Stub(proc.address) as stub:
                stub.call('SHUTDOWN')
            proc.wait()

if __name__ == '__main__':
    unittest.main()
