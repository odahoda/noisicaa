from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

import unittest
import sys

from noisicaa.core.status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *
from .message_queue cimport *

class TestProcessorSoundFile(unittest.TestCase):
    def test_sound_file(self):
        cdef Status status

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'sound_file')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())
        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'out:left', PortType.audio, PortDirection.Output)
        spec.get().add_port(b'out:right', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'sound_file_path', b'/usr/share/sounds/purple/send.wav'))

        check(processor.setup(spec.release()))

        cdef float outleftbuf[128]
        cdef float outrightbuf[128]

        check(processor.connect_port(0, <BufferPtr>outleftbuf))
        check(processor.connect_port(1, <BufferPtr>outrightbuf))

        for i in range(128):
            outleftbuf[i] = 0.0
            outrightbuf[i] = 0.0

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 128

        cdef Message* msg
        done = False
        while not done:
            check(processor.run(ctxt.get()))

            msg = ctxt.get().out_messages.get().first()
            while not ctxt.get().out_messages.get().is_end(msg):
                if msg.type == MessageType.SOUND_FILE_COMPLETE:
                    done = True
                msg = ctxt.get().out_messages.get().next(msg)

        self.assertTrue(any(v != 0.0 for v in outleftbuf))
        self.assertTrue(any(v != 0.0 for v in outrightbuf))

        processor.cleanup()
