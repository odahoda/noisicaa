#!/usr/bin/python3

import os
import signal
import time

from .. import node


class PipelineCrasher(node.Node):
    class_name = 'pipeline_crasher'

    def run(self, ctxt):
        trigger = self.get_param('trigger')
        if trigger > 0.5:
            raise RuntimeError("Kaboom!")
        if trigger < -0.5:
            os.kill(os.getpid(), signal.SIGSEGV)
            time.sleep(10)

        input_port = self.inputs['in']
        output_port = self.outputs['out']
        output_port.frame.resize(ctxt.duration)
        output_port.frame.copy_from(input_port.frame)
