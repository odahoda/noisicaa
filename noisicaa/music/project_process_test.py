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


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.mgr = core.ProcessManager()
        self.mgr.setup()
        self.proc = self.mgr.start_process(
            'test', project_process.ProjectProcess)
        self.stub = project_stub.ProjectStub(self.proc.address)
        self.stub.connect()

    def tearDown(self):
        self.stub.shutdown()
        self.stub.close()
        self.mgr.cleanup()

    def test_root_proxy(self):
        proxy = self.stub.project
        self.assertEqual(proxy.current_sheet, 0)

    def test_fetch_proxy(self):
        proxy = self.stub.project.metadata
        self.assertIsNone(proxy.author)


if __name__ == '__main__':
    unittest.main()
