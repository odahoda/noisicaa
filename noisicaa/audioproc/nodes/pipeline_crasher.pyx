#!/usr/bin/python3

import os
import signal
import time

from .. cimport node


cdef class PipelineCrasher(node.CustomNode):
    class_name = 'pipeline_crasher'

    cdef int run(self, ctxt) except -1:
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

        return 0
