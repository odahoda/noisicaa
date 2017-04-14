#!/usr/bin/python3

import time
import unittest

import asynctest

from . import pipeline_vm


class PipelineVMTest(asynctest.TestCase):
    async def test_foo(self):
        vm = pipeline_vm.PipelineVM()
        try:
            vm.setup()

            spec = pipeline_vm.PipelineVMSpec()
            spec.opcodes.append(pipeline_vm.OpCode())
            vm.set_spec(spec)

            time.sleep(1)

        finally:
            vm.cleanup()


if __name__ == '__main__':
    unittest.main()
